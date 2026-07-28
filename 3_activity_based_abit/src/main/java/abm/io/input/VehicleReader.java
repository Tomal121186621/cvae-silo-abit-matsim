package abm.io.input;

import abm.data.DataSet;
import abm.data.pop.*;
import abm.data.vehicle.Car;
import abm.data.vehicle.CarType;
import abm.data.vehicle.VehicleUtil;
import abm.properties.AbitResources;
import de.tum.bgu.msm.data.person.Disability;
import de.tum.bgu.msm.data.person.Gender;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.util.MitoUtil;
import org.apache.log4j.Logger;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

public class VehicleReader implements Reader {

    private final DataSet dataSet;
    private final Map<String, Integer> indexes;
    final String path;
    private BufferedReader br;

    final static String REGEX = ",";
    private Logger logger = Logger.getLogger(VehicleReader.class);

    public VehicleReader(DataSet dataSet) {
        this.dataSet = dataSet;
        indexes = new HashMap<>();
        path = AbitResources.instance.getString("vehicles.file");
    }

    @Override
    public void read() {
        try {
            br = new BufferedReader(new FileReader(path));
            logger.info("Reading from " + path);
            processHeader(br, indexes);
            processRecords(br, indexes, dataSet);
        } catch (IOException e) {
            e.printStackTrace();
        }

    }

    private void processHeader(BufferedReader br, Map<String, Integer> indexes) throws IOException {
        String[] header = br.readLine().split(REGEX);

        indexes.put("hhId", MitoUtil.findPositionInArray("id", header));
        //indexes.put("hhId", MitoUtil.findPositionInArray("hh", header));
        indexes.put("numAutos", MitoUtil.findPositionInArray("autos", header));
        indexes.put("index", MitoUtil.findPositionInArray("index", header));
        indexes.put("vehId", MitoUtil.findPositionInArray("vehId", header));
        indexes.put("type", MitoUtil.findPositionInArray("type", header));
        indexes.put("age", MitoUtil.findPositionInArray("age", header));

    }


    private void processRecords(BufferedReader br, Map<String, Integer> indexes, DataSet dataSet) throws IOException {

        String line;
        while ((line = br.readLine()) != null) {

            String[] splitLine = line.split(REGEX);

            int id = Integer.parseInt(splitLine[indexes.get("index")]);
            int hhid = Integer.parseInt(splitLine[indexes.get("hhId")]);


            Household hh = dataSet.getHouseholds().getOrDefault(hhid, null);

            if (hh == null) {
                throw new RuntimeException("The household does not exist");
            }

            int numAutos = Integer.parseInt(splitLine[indexes.get("numAutos")]);
            String vehType = splitLine[indexes.get("type")].toUpperCase();


            if (numAutos != hh.getNumberOfCars()) {
                throw new RuntimeException("Number of cars in hh and vv doesn't match, hh id: " + hh.getId());
            } else {
                if (vehType.equals("CONVENTIONAL")) {
                    hh.getVehicles().add(new Car(id, CarType.CONVENTIONAL, VehicleUtil.getVehicleAgeInBaseYear()));
                } else if (vehType.equals("ELECTRIC")) {
                    hh.getVehicles().add(new Car(id, CarType.ELECTRIC, VehicleUtil.getVehicleAgeInBaseYear()));
                }
            }
        }
    }
}
