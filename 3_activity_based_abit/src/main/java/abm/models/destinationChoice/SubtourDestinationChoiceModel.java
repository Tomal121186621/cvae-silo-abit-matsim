package abm.models.destinationChoice;

import abm.data.DataSet;
import abm.data.geo.MicroscopicLocation;
import abm.data.geo.Zone;
import abm.data.plans.Activity;
import abm.data.plans.Mode;
import abm.data.plans.Purpose;
import abm.data.pop.Household;
import abm.io.input.CoefficientsReader;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.util.MitoUtil;
import de.tum.bgu.msm.util.matrices.IndexedDoubleMatrix2D;
import org.apache.log4j.Logger;
import org.locationtech.jts.geom.Coordinate;

import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

public class SubtourDestinationChoiceModel implements SubtourDestinationChoice {

    private final DataSet dataSet;
    private final static Logger logger = Logger.getLogger(DestinationChoiceModel.class);
    private final Map<Zone, Double> zoneAttractors;
    private IndexedDoubleMatrix2D utilityMatrix;
    private Map<Purpose, Map<String, Double>> coefficientsSubtourDestination;
    private static final double BETA = -0.8573;
    private boolean runCalibration = false;
    public SubtourDestinationChoiceModel(DataSet dataSet) {
        this.dataSet = dataSet;

        this.coefficientsSubtourDestination = new HashMap<>();
        Path pathToFilePurpose = Path.of(AbitResources.instance.getString("subtour.destination.output"));
        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            final Map<String, Double> purposeCoefficientsMain = new CoefficientsReader(dataSet, purpose.toString().toLowerCase(), pathToFilePurpose).readCoefficients();
            coefficientsSubtourDestination.put(purpose, purposeCoefficientsMain);
        }

        zoneAttractors = loadBasicAttraction();
        utilityMatrix = loadUtilities();
    }

    public SubtourDestinationChoiceModel(DataSet dataSet, boolean runCalibration) {
        this(dataSet);
        this.runCalibration = runCalibration;

    }


    @Override
    public void chooseSubtourDestination(Activity subtourActivity, Activity mainActivity) {
        Zone origin = dataSet.getZones().get(mainActivity.getLocation().getZoneId());

        final int selectedIndex = MitoUtil.select(utilityMatrix.viewRow(origin.getId()).toNonIndexedArray());

        final int[] columnLookupArray = utilityMatrix.getColumnLookupArray();

        Zone destination = dataSet.getZones().get(columnLookupArray[selectedIndex]);

        final Coordinate randomCoordinate = destination.getRandomCoordinate(AbitUtils.getRandomObject());
        MicroscopicLocation microDestination = new MicroscopicLocation(randomCoordinate.x, randomCoordinate.y);
        microDestination.setZone(destination);
        subtourActivity.setLocation(microDestination);
    }

    private IndexedDoubleMatrix2D loadUtilities() {

        IndexedDoubleMatrix2D utilityMatrix = new IndexedDoubleMatrix2D(dataSet.getZones().values(), dataSet.getZones().values());
        for (Zone origin : dataSet.getZones().values()) {
            for (Zone destination : dataSet.getZones().values()) {
                final int travelDistanceInMeters = dataSet.getTravelDistances().getTravelDistanceInMeters(origin, destination, Mode.UNKNOWN, 0.);
                final double attractor = zoneAttractors.get(destination);
                double utility = attractor * Math.exp((BETA + coefficientsSubtourDestination.get(Purpose.WORK).get("calibration")) * (double)(travelDistanceInMeters/1000));
                utilityMatrix.setIndexed(origin.getId(), destination.getId(), utility);
            }
        }

        return utilityMatrix;
    }

    private Map<Zone, Double> loadBasicAttraction() {

        Map<Zone, Double> zoneAttractors = new HashMap<>();
        for (Zone z : dataSet.getZones().values()) {
            zoneAttractors.put(z, 0.);
        }
        for (Household household : dataSet.getHouseholds().values()) {
            Zone zone = dataSet.getZones().get(household.getLocation().getZoneId());
            zoneAttractors.put(zone, zoneAttractors.get(zone) + household.getPersons().size());
        }
        return zoneAttractors;
    }

    public void updateUtilities() {
        utilityMatrix = loadUtilities();
    }

    public void updateCalibration(Map<Purpose, Double> newCalibrationFactorsMain) {
        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            double calibrationFactorsFromLastIteration = this.coefficientsSubtourDestination.get(purpose).get("calibration");
            double updatedCalibrationFactors = newCalibrationFactorsMain.get(Purpose.WORK);
            this.coefficientsSubtourDestination.get(purpose).replace("calibration", calibrationFactorsFromLastIteration + updatedCalibrationFactors);
            logger.info("Calibration factor for " + purpose + "\t" + ": " + updatedCalibrationFactors);
        }

    }

    public Map<Purpose, Double> obtainCoefficientsTable() {

        Map<Purpose, Double> coefficientsTable = new HashMap<>();
        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            coefficientsTable.put(purpose, this.coefficientsSubtourDestination.get(purpose).get("calibration"));
        }

        return coefficientsTable;
    }


}
