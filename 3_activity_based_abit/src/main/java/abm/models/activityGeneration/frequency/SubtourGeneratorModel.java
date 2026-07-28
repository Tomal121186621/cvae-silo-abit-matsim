package abm.models.activityGeneration.frequency;

import abm.data.DataSet;
import abm.data.plans.*;
import abm.data.pop.EmploymentStatus;
import abm.data.pop.Person;
import abm.io.input.CoefficientsReader;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.util.MitoUtil;
import org.apache.log4j.Logger;

import java.nio.file.Path;
import java.time.DayOfWeek;
import java.util.HashMap;
import java.util.Map;

public class SubtourGeneratorModel implements SubtourGenerator {

    private static final Logger logger = Logger.getLogger(SubtourGeneratorModel.class);

    private final DataSet dataSet;

    private boolean runCalibration = false;

    private Map<Purpose, Map<Boolean, Double>> updatedCalibrationFactors;

    private Map<String, Double> workSubtourCoef;
    private Map<String, Double> eduSubtourCoef;

    public SubtourGeneratorModel(DataSet dataSet) {
        this.dataSet = dataSet;

        this.workSubtourCoef =
                new CoefficientsReader(dataSet, "yes",
                        Path.of(AbitResources.instance.getString("actgen.subtour.work"))).readCoefficients();

        this.eduSubtourCoef =
                new CoefficientsReader(dataSet, "yes",
                        Path.of(AbitResources.instance.getString("actgen.subtour.education"))).readCoefficients();

    }

    public SubtourGeneratorModel(DataSet dataSet, Boolean runCalibration) {
        this(dataSet);
        this.updatedCalibrationFactors = new HashMap<>();
        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            this.updatedCalibrationFactors.putIfAbsent(purpose, new HashMap<>());
            this.updatedCalibrationFactors.get(purpose).putIfAbsent(Boolean.TRUE, 0.0);
            this.updatedCalibrationFactors.get(purpose).putIfAbsent(Boolean.FALSE, 0.0);
        }
        this.runCalibration = runCalibration;
    }

    @Override
    public boolean hasSubtourInMandatoryActivity(Tour mandatoryTour) {


        Person person = mandatoryTour.getMainActivity().getPerson();
        Purpose purpose = mandatoryTour.getMainActivity().getPurpose();
        double utility = calculateUtility(purpose, person, mandatoryTour);


        HashMap<Boolean, Double> probabilities = new HashMap<>();
        probabilities.put(false, Math.exp(0));
        probabilities.put(true, Math.exp(utility));
        boolean hasSubtour = MitoUtil.select(probabilities, AbitUtils.getRandomObject());

        if (mandatoryTour.getMainActivity().getEndTime_min() - mandatoryTour.getMainActivity().getStartTime_min() < 3 * 60) {
            hasSubtour = false;
        }
        if (mandatoryTour.getMainActivity().getStartTime_min() < 0) {
            hasSubtour = false;
        }

        return hasSubtour;

    }

    private double calculateUtility(Purpose purpose, Person person, Tour mandatoryTour) {

        double utility = 0.;
        Activity mandatoryActivity = mandatoryTour.getMainActivity();
        int dayOfWeekOffset = (mandatoryActivity.getDayOfWeek().getValue() - 1) * 60 * 24;

        if (purpose.equals(Purpose.WORK)) {

            utility += workSubtourCoef.get("ASC");

            if (mandatoryActivity.getDuration() > 6 * 60 && mandatoryActivity.getDuration() < 24 * 60) {
                utility += workSubtourCoef.get("actDuration_6_24");
            }

            if (mandatoryActivity.getStartTime_min() - dayOfWeekOffset > 8 * 60 && mandatoryActivity.getStartTime_min() - dayOfWeekOffset < 12 * 60) {
                utility += workSubtourCoef.get("actStart_8_12");
            }

            if (mandatoryActivity.getEndTime_min() - dayOfWeekOffset > 12 * 60 && mandatoryActivity.getEndTime_min() - dayOfWeekOffset < 24 * 60) {
                utility += workSubtourCoef.get("actEnd_12_24");
            }

            if (mandatoryActivity.getDayOfWeek().equals(DayOfWeek.FRIDAY)) {
                utility += workSubtourCoef.get("isTourOnFriday");
            } else if (mandatoryActivity.getDayOfWeek().equals(DayOfWeek.SATURDAY)) {
                utility += workSubtourCoef.get("isTourOnWeekend");
            } else if (mandatoryActivity.getDayOfWeek().equals(DayOfWeek.SUNDAY)) {
                utility += workSubtourCoef.get("isTourOnWeekend");
            }

            if (person.getEmploymentStatus().equals(EmploymentStatus.HALFTIME_EMPLOYED)) {
                utility += workSubtourCoef.get("isOccupation_halftime");
            } else if (person.getOccupation().equals(Occupation.STUDENT)) {
                utility += workSubtourCoef.get("isOccupation_student");
            }

            //todo add travel time from work location to pt: "isWorkplaceToPtStop>20min"

            utility += workSubtourCoef.get("calibration");

            if (runCalibration) {
                utility += updatedCalibrationFactors.get(purpose).get(Boolean.TRUE);
            }

        } else if (purpose.equals(Purpose.EDUCATION)) {

            utility += eduSubtourCoef.get("ASC");

            if (mandatoryActivity.getStartTime_min() - dayOfWeekOffset > 7 * 60 && mandatoryActivity.getStartTime_min() - dayOfWeekOffset < 12 * 60) {
                utility += eduSubtourCoef.get("actStart_7_12");
            }

            if (mandatoryActivity.getEndTime_min() - dayOfWeekOffset > 12 * 60 && mandatoryActivity.getEndTime_min() - dayOfWeekOffset < 24 * 60) {
                utility += eduSubtourCoef.get("actEnd_12_24");
            }

            //todo add travel time from work location to pt: "isSchoolplaceToPtStop>20min♦"

            if (person.getAge() < 16) {
                utility += eduSubtourCoef.get("isAge<16");
            }

            utility += eduSubtourCoef.get("calibration");

            if (runCalibration) {
                utility += updatedCalibrationFactors.get(purpose).get(Boolean.TRUE);
            }

        }
        return utility;
    }

    public void updateCalibrationFactor(Map<Purpose, Map<Boolean, Double>> newCalibrationFactors) {
        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            double calibrationFactorFromLastIteration = this.updatedCalibrationFactors.get(purpose).get(Boolean.TRUE);
            double updatedCalibrationFactor = newCalibrationFactors.get(purpose).get(Boolean.TRUE) + calibrationFactorFromLastIteration;
            this.updatedCalibrationFactors.get(purpose).replace(Boolean.TRUE, updatedCalibrationFactor);
            logger.info("Calibration factor for " + purpose + "\t" + "and " + Boolean.TRUE + "\t" + ": " + updatedCalibrationFactor);
        }
    }

    public Map<Purpose, Map<String, Double>> obtainCoefficientsTable() {

        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            double originalCalibrationFactor = 0.0;
            double updatedCalibrationFactor = 0.0;
            double latestCalibrationFactor = 0.0;

            if (purpose.equals(Purpose.WORK)) {
                originalCalibrationFactor = this.workSubtourCoef.get("calibration");
                updatedCalibrationFactor = updatedCalibrationFactors.get(purpose).get(Boolean.TRUE);
                latestCalibrationFactor = originalCalibrationFactor + updatedCalibrationFactor;
                this.workSubtourCoef.replace("calibration", latestCalibrationFactor);
            } else {
                originalCalibrationFactor = this.eduSubtourCoef.get("calibration");
                updatedCalibrationFactor = updatedCalibrationFactors.get(purpose).get(Boolean.TRUE);
                latestCalibrationFactor = originalCalibrationFactor + updatedCalibrationFactor;
                this.eduSubtourCoef.replace("calibration", latestCalibrationFactor);
            }
        }

        Map<Purpose, Map<String, Double>> subtourCoefficients = new HashMap<>();
        subtourCoefficients.put(Purpose.WORK, this.workSubtourCoef);
        subtourCoefficients.put(Purpose.EDUCATION, this.eduSubtourCoef);
        return subtourCoefficients;
    }
}
