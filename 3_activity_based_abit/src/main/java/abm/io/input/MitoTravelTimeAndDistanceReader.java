package abm.io.input;


import abm.data.DataSet;
import abm.data.plans.Mode;
import abm.data.travelInformation.MitoBasedTravelDistances;
import abm.data.travelInformation.MitoBasedTravelTimes;
import abm.properties.AbitResources;
import de.tum.bgu.msm.data.travelTimes.SkimTravelTimes;

public class MitoTravelTimeAndDistanceReader implements Reader {


    private final DataSet dataSet;

    public MitoTravelTimeAndDistanceReader(DataSet dataSet) {
        this.dataSet = dataSet;
    }


    @Override
    public void read() {

        //todo temporary factors for testing
//        double busFactor = 0.35;
//        double tramMetroFactor = 0.6;
//        double trainFactor = 0.75;


        SkimTravelTimes travelTimes = new SkimTravelTimes();

        String carFile = AbitResources.instance.getString("car.omx.file");
        String carMatrixName  = AbitResources.instance.getString("car.omx.matrix");
        travelTimes.readSkim(Mode.CAR_DRIVER.toString(), carFile, carMatrixName, 1/60.);

        String busFile  = AbitResources.instance.getString("bus.omx.file");
        String busMatrixName  = AbitResources.instance.getString("bus.omx.matrix");
        travelTimes.readSkim(Mode.BUS.toString(), busFile, busMatrixName, 1/60.);

        String tramMetroFile  = AbitResources.instance.getString("tramMetro.omx.file");
        String tramMetroMatrixName  = AbitResources.instance.getString("tramMetro.omx.matrix");
        travelTimes.readSkim(Mode.TRAM_METRO.toString(), tramMetroFile, tramMetroMatrixName, 1/60.);

        String trainFile  = AbitResources.instance.getString("train.omx.file");
        String trainMatrixName  = AbitResources.instance.getString("train.omx.matrix");
        travelTimes.readSkim(Mode.TRAIN.toString(), trainFile, trainMatrixName, 1/60.);

        dataSet.setTravelTimes(new MitoBasedTravelTimes(travelTimes));

        //it is using the traveltimes but this is distance!
        SkimTravelTimes travelDistances = new SkimTravelTimes();
        String nonMotorizedFile = AbitResources.instance.getString("car.omx.file");
        String nonMotorizedMatrixName  = AbitResources.instance.getString("car.distance.omx.matrix");
        travelDistances.readSkim(Mode.UNKNOWN.toString(), nonMotorizedFile, nonMotorizedMatrixName, 1.);

        dataSet.setTravelDistances(new MitoBasedTravelDistances(travelDistances));


    }
}
