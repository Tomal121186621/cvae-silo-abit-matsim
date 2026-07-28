package abm.io.input;

import abm.data.DataSet;
import abm.data.geo.MicroscopicLocation;
import abm.data.pop.Job;
import abm.data.pop.School;
import abm.properties.AbitResources;
import de.tum.bgu.msm.util.MitoUtil;
import org.apache.log4j.Logger;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

public class SchoolReader implements Reader {

    private static Logger logger = Logger.getLogger(SchoolReader.class);

    private final DataSet dataSet;
    private final Map<String, Integer>  indexes;
    final String path;
    private BufferedReader br;

    final static String REGEX = ",";

    public SchoolReader(DataSet dataSet) {
        this.dataSet = dataSet;
        indexes = new HashMap<>();
        path = AbitResources.instance.getString("schools.file");
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

    private void processHeader(BufferedReader br, Map<String, Integer>  indexes) throws IOException {
        String[] header = br.readLine().split(REGEX);

        indexes.put("id", MitoUtil.findPositionInArray("id", header));
        indexes.put("zone", MitoUtil.findPositionInArray("zone", header));
        indexes.put("type", MitoUtil.findPositionInArray("type", header));
        indexes.put("capacity", MitoUtil.findPositionInArray("capacity", header));
        indexes.put("occupancy", MitoUtil.findPositionInArray("occupancy", header));
        indexes.put("coordX", MitoUtil.findPositionInArray("coordX", header));
        indexes.put("coordY", MitoUtil.findPositionInArray("coordY", header));
        indexes.put("startTime", MitoUtil.findPositionInArray("startTime", header));
        indexes.put("duration", MitoUtil.findPositionInArray("duration", header));

    }


    private void processRecords(BufferedReader br, Map<String, Integer>  indexes, DataSet dataSet) throws IOException {

        String line;
        while ((line = br.readLine())!= null){

            String[] splitLine = line.split(REGEX);

            int id = Integer.parseInt(splitLine[indexes.get("id")]);
            int zoneId = Integer.parseInt(splitLine[indexes.get("zone")]);

            String type = splitLine[indexes.get("type")].replace("\"","");

            double x = Double.parseDouble(splitLine[indexes.get("coordX")]);
            double y = Double.parseDouble(splitLine[indexes.get("coordY")]);

            int capacity = Integer.parseInt(splitLine[indexes.get("capacity")]);
            int occupancy = Integer.parseInt(splitLine[indexes.get("occupancy")]);

            MicroscopicLocation location = new MicroscopicLocation(x, y);
            location.setZone(dataSet.getZones().get(zoneId));

            int startTime_min = (int) (Double.parseDouble(splitLine[indexes.get("startTime")])/60.);
            int duration_min = (int)  (Double.parseDouble(splitLine[indexes.get("duration")])/60.);

            School school = new School(id, type, capacity, occupancy, location, startTime_min, duration_min);

            dataSet.getSchools().put(id, school);

        }

    }
}
