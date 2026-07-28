package abm.calibration;

import abm.data.DataSet;

import abm.properties.AbitResources;

import org.apache.log4j.Logger;

import java.io.FileNotFoundException;
import java.util.HashMap;
import java.util.Map;


public class CalibrationMuc {

    static Logger logger = Logger.getLogger(CalibrationMuc.class);
    DataSet dataSet;

    //Todo add booleans for all the models that need to be calibrated here:
    boolean calibrateHabitualModeChoice;
    boolean calibrateMandatoryActGeneration;
    boolean calibrateMandatoryActDayOfWeekAssignment;
    boolean calibrateMandatoryActStartTime;
    boolean calibrateMandatoryActDurationTime;
    boolean calibrateMainDestinationChoice;
    boolean calibrateStopDestinationChoice;
    boolean calibrateMainMcLogsumDestinationChoice;
    boolean calibrateStopMcLogsumDestinationChoice;
    boolean calibrateDiscretionaryActGeneration;
    boolean calibrateDiscretionaryActSplitByType;
    boolean calibrateDiscretionaryActDayOfWeekAssignment;
    boolean calibrateDiscretionaryActStartTime;
    boolean calibrateDiscretionaryActDuration;
    boolean calibrateDiscretionaryActStopType;
    boolean calibrateTourModeChoice;
    boolean calibrateSubTourGeneration;
    boolean calibrateSubTourStartTime;
    boolean calibrateSubTourDuration;
    boolean calibrateSubTourDestinationChoice;
    boolean calibrateSubTourModeChoice;


    //Todo add all the calibration class here
    private HabitualModeChoiceCalibration habitualModeChoiceCalibration;
    private FrequencyGeneratorCalibration frequencyGeneratorCalibration;
    private DayOfWeekMandatoryAssignmentCalibration dayOfWeekMandatoryAssignmentCalibration;
    private DayOfWeekDiscretionaryAssignmentCalibration dayOfWeekDiscretionaryAssignmentCalibration;
    private TimeAssignmentCalibration timeAssignmentCalibration;
    private MainDestinationChoiceCalibration mainDestinationChoiceCalibration;
    private StopDestinationChoiceCalibration stopDestinationChoiceCalibration;

    private StopMcLogsumDestinationChoiceCalibration stopMcLogsumDestinationChoiceCalibration;

    private MainMcLogsumDestinationChoiceCalibration mainMcLogsumDestinationChoiceCalibration;
    private SplitByTypeCalibration splitByTypeCalibration;
    private SplitStopByTypeCalibration splitStopByTypeCalibration;
    private TourModeChoiceCalibration tourModeChoiceCalibration;
    private SubTourGenerationCalibration subTourGenerationCalibration;
    private SubTourTimeAssignmentCalibration subTourTimeAssignmentCalibration;
    private SubTourDestinationChoiceCalibration subTourDestinationChoiceCalibration;
    private SubTourModeChoiceCalibration subTourModeChoiceCalibration;

    private final Map<String, Boolean> calibrationList = new HashMap<>();

    public CalibrationMuc(DataSet dataSet) {
        this.dataSet = dataSet;

        calibrateHabitualModeChoice = Boolean.parseBoolean(AbitResources.instance.getString("habitual.mode.calibration"));
        calibrationList.put("HabitualModeChoice", calibrateHabitualModeChoice);

        calibrateMandatoryActGeneration = Boolean.parseBoolean(AbitResources.instance.getString("actgen.mand.calibration"));
        calibrationList.put("ManActGeneration", calibrateMandatoryActGeneration);

        calibrateMandatoryActDayOfWeekAssignment = Boolean.parseBoolean(AbitResources.instance.getString("day.of.week.mandatory.acts.calibration"));
        calibrationList.put("ManActDayOfWeek", calibrateMandatoryActDayOfWeekAssignment);

        calibrateMandatoryActStartTime = Boolean.parseBoolean(AbitResources.instance.getString("act.mand.start.time.calibration"));
        calibrationList.put("ManActStartTime", calibrateMandatoryActStartTime);

        calibrateMandatoryActDurationTime = Boolean.parseBoolean(AbitResources.instance.getString("act.mand.duration.calibration"));
        calibrationList.put("ManActDuration", calibrateMandatoryActDurationTime);

        calibrateMainDestinationChoice = Boolean.parseBoolean(AbitResources.instance.getString("act.main.destination.calibration"));
        calibrationList.put("MainActDestination", calibrateMainDestinationChoice);

        calibrateStopDestinationChoice = Boolean.parseBoolean(AbitResources.instance.getString("act.stop.destination.calibration"));
        calibrationList.put("StopDestination", calibrateStopDestinationChoice);

        calibrateMainMcLogsumDestinationChoice = Boolean.parseBoolean(AbitResources.instance.getString("act.main.mcLogsum.destination.calibration"));
        calibrationList.put("McLogsumMainActDestination", calibrateMainMcLogsumDestinationChoice);

        calibrateStopMcLogsumDestinationChoice = Boolean.parseBoolean(AbitResources.instance.getString("act.stop.mcLogsum.destination.calibration"));
        calibrationList.put("McLogsumStopActDestination", calibrateStopMcLogsumDestinationChoice);

        calibrateDiscretionaryActGeneration = Boolean.parseBoolean(AbitResources.instance.getString("actgen.disc.calibration"));
        calibrationList.put("DiscActGeneration", calibrateDiscretionaryActGeneration);

        calibrateDiscretionaryActSplitByType = Boolean.parseBoolean(AbitResources.instance.getString("act.split.type.calibration"));
        calibrationList.put("DiscActSplitByType", calibrateDiscretionaryActSplitByType);

        calibrateDiscretionaryActDayOfWeekAssignment = Boolean.parseBoolean(AbitResources.instance.getString("act.split.type.onto.discretionary.calibration"));
        calibrationList.put("DiscActDayOfWeek", calibrateDiscretionaryActDayOfWeekAssignment);

        calibrateDiscretionaryActStartTime = Boolean.parseBoolean(AbitResources.instance.getString("act.disc.start.time.calibration"));
        calibrationList.put("DiscActStartTime", calibrateDiscretionaryActStartTime);

        calibrateDiscretionaryActDuration = Boolean.parseBoolean(AbitResources.instance.getString("act.disc.duration.calibration"));
        calibrationList.put("DiscActDuration", calibrateDiscretionaryActDuration);

        calibrateDiscretionaryActStopType = Boolean.parseBoolean(AbitResources.instance.getString("act.split.stop.type.calibration"));
        calibrationList.put("DiscActStopOnto", calibrateDiscretionaryActStopType);

        calibrateTourModeChoice = Boolean.parseBoolean(AbitResources.instance.getString("tour.mode.calibration"));
        calibrationList.put("TourModeChoice", calibrateTourModeChoice);

        calibrateSubTourGeneration = Boolean.parseBoolean(AbitResources.instance.getString("actgen.subtour.calibration"));
        calibrationList.put("SubTourGeneration", calibrateSubTourGeneration);

        calibrateSubTourStartTime = Boolean.parseBoolean(AbitResources.instance.getString("start.time.subtour.calibration"));
        calibrationList.put("SubTourStartTime", calibrateSubTourStartTime);

        calibrateSubTourDuration = Boolean.parseBoolean(AbitResources.instance.getString("act.duration.subtour.calibration"));
        calibrationList.put("SubTourDuration", calibrateSubTourDuration);

        calibrateSubTourDestinationChoice = Boolean.parseBoolean(AbitResources.instance.getString("subtour.destination.calibration"));
        calibrationList.put("SubTourDestination", calibrateSubTourDestinationChoice);

        calibrateSubTourModeChoice = Boolean.parseBoolean(AbitResources.instance.getString("mode.choice.subtour.calibration"));
        calibrationList.put("SubTourModeChoice", calibrateSubTourDestinationChoice);

    }


    public void runCalibration() throws FileNotFoundException {

        //checkCalibrationProcess();

        if (calibrateHabitualModeChoice) {
            habitualModeChoiceCalibration = new HabitualModeChoiceCalibration(dataSet);
            habitualModeChoiceCalibration.setup();
            habitualModeChoiceCalibration.load();
            habitualModeChoiceCalibration.run();
        }

        if (calibrateMandatoryActGeneration || calibrateDiscretionaryActGeneration) {
            frequencyGeneratorCalibration = new FrequencyGeneratorCalibration(dataSet);
            frequencyGeneratorCalibration.setup();
            frequencyGeneratorCalibration.load();
            frequencyGeneratorCalibration.run();
        }

//        if (calibrateMandatoryActDayOfWeekAssignment) {
//            dayOfWeekMandatoryAssignmentCalibration = new DayOfWeekMandatoryAssignmentCalibration();
//            dayOfWeekMandatoryAssignmentCalibration.setup();
//            dayOfWeekMandatoryAssignmentCalibration.load();
//            dayOfWeekMandatoryAssignmentCalibration.run();
//        }

//        if (calibrateMandatoryActStartTime || calibrateMandatoryActDurationTime) {
//            timeAssignmentCalibration = new TimeAssignmentCalibration();
//            timeAssignmentCalibration.setup();
//            timeAssignmentCalibration.load();
//            timeAssignmentCalibration.run();
//        }


        if (calibrateDiscretionaryActSplitByType) {
            splitByTypeCalibration = new SplitByTypeCalibration(dataSet);
            splitByTypeCalibration.setup();
            splitByTypeCalibration.load();
            splitByTypeCalibration.run();
        }

//        if (calibrateDiscretionaryActDayOfWeekAssignment) {
//            dayOfWeekDiscretionaryAssignmentCalibration = new DayOfWeekDiscretionaryAssignmentCalibration();
//            dayOfWeekDiscretionaryAssignmentCalibration.setup();
//            dayOfWeekDiscretionaryAssignmentCalibration.load();
//            dayOfWeekDiscretionaryAssignmentCalibration.run();
//        }

//        if (calibrateDiscretionaryActStartTime || calibrateDiscretionaryActDuration){
//            timeAssignmentCalibration = new TimeAssignmentCalibration();
//            timeAssignmentCalibration.setup();
//            timeAssignmentCalibration.load();
//            timeAssignmentCalibration.run();
//        }

//        if (calibrateDiscretionaryActStopType){
//            splitStopByTypeCalibration = new SplitStopByTypeCalibration(dataSet);
//            splitStopByTypeCalibration.setup();
//            splitStopByTypeCalibration.load();
//            splitStopByTypeCalibration.run();
//        }

        if (calibrateMainDestinationChoice){
            mainDestinationChoiceCalibration = new MainDestinationChoiceCalibration(dataSet);
            mainDestinationChoiceCalibration.setup();
            mainDestinationChoiceCalibration.load();
            mainDestinationChoiceCalibration.run();
        }

        if (calibrateStopDestinationChoice){
            stopDestinationChoiceCalibration = new StopDestinationChoiceCalibration(dataSet);
            stopDestinationChoiceCalibration.setup();
            stopDestinationChoiceCalibration.load();
            stopDestinationChoiceCalibration.run();
        }

        if (calibrateMainMcLogsumDestinationChoice){
            mainMcLogsumDestinationChoiceCalibration = new MainMcLogsumDestinationChoiceCalibration(dataSet);
            mainMcLogsumDestinationChoiceCalibration.setup();
            mainMcLogsumDestinationChoiceCalibration.load();
            mainMcLogsumDestinationChoiceCalibration.run();
        }

        if (calibrateStopMcLogsumDestinationChoice){
            stopMcLogsumDestinationChoiceCalibration = new StopMcLogsumDestinationChoiceCalibration(dataSet);
            stopMcLogsumDestinationChoiceCalibration.setup();
            stopMcLogsumDestinationChoiceCalibration.load();
            stopMcLogsumDestinationChoiceCalibration.run();
        }

        if (calibrateTourModeChoice){
            tourModeChoiceCalibration = new TourModeChoiceCalibration(dataSet);
            tourModeChoiceCalibration.setup();
            tourModeChoiceCalibration.load();
            tourModeChoiceCalibration.run();
        }

        if (calibrateSubTourGeneration){
            subTourGenerationCalibration = new SubTourGenerationCalibration(dataSet);
            subTourGenerationCalibration.setup();
            subTourGenerationCalibration.load();
            subTourGenerationCalibration.run();
        }

//        if (calibrateSubTourStartTime || calibrateSubTourDuration){
//            subTourTimeAssignmentCalibration = new SubTourTimeAssignmentCalibration();
//            subTourTimeAssignmentCalibration.setup();
//            subTourTimeAssignmentCalibration.load();
//            subTourTimeAssignmentCalibration.run();
//        }

        if (calibrateSubTourDestinationChoice){
            subTourDestinationChoiceCalibration = new SubTourDestinationChoiceCalibration(dataSet);
            subTourDestinationChoiceCalibration.setup();
            subTourDestinationChoiceCalibration.load();
            subTourDestinationChoiceCalibration.run();
        }

        if (calibrateSubTourModeChoice){
            subTourModeChoiceCalibration = new SubTourModeChoiceCalibration(dataSet);
            subTourModeChoiceCalibration.setup();
            subTourModeChoiceCalibration.load();
            subTourModeChoiceCalibration.run();
        }

    }

    private void checkCalibrationProcess() {

        String startPointOfCalibration = null;
        boolean calibrateStatus = false;

        for (Map.Entry<String, Boolean> entry : calibrationList.entrySet()) {
            if (entry.getValue()) {
                startPointOfCalibration = entry.getKey();
                logger.info("Calibration starts from the " + startPointOfCalibration);
                break;
            }
        }

        for (Map.Entry<String, Boolean> entry : calibrationList.entrySet()) {
            if (entry.getKey().equals(startPointOfCalibration)) {
                calibrateStatus = true;
            }
            if (calibrateStatus) {
                if (!entry.getValue()) {
                    System.err.println(entry.getKey() + " needs to be calibrated as well.");
                    calibrationList.replace(entry.getKey(), Boolean.TRUE);
                    logger.info("Calibration of " + entry.getKey() + " has been set to true");
                }
            }
        }
    }
}
