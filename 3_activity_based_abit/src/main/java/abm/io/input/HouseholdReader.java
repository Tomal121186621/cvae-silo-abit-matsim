package abm.io.input;

import abm.data.DataSet;
import abm.data.geo.MicroscopicLocation;
import abm.data.pop.*;
import abm.properties.AbitResources;
import de.tum.bgu.msm.util.MitoUtil;
import org.apache.log4j.Logger;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

public class HouseholdReader implements Reader {

    private final DataSet dataSet;
    private final Map<String, Integer> indexesHh;
    private final Map<String, Integer> indexesDd;
    private final String pathDdFile;
    Map<Integer, Dwelling> dwellings = new HashMap<>();
    final String pathHhFile;
    private BufferedReader brHh;
    private BufferedReader brDd;

    private final Logger logger = Logger.getLogger(HouseholdReader.class);

    final static String REGEX = ",";

    public HouseholdReader(DataSet dataSet) {
        this.dataSet = dataSet;
        indexesHh = new HashMap<>();
        indexesDd = new HashMap<>();
        pathDdFile = AbitResources.instance.getString("dwellings.file");
        pathHhFile = AbitResources.instance.getString("households.file");


    }

    @Override
    public void read() {
        try {
            //read first dwellings to find out coordinates
            brDd = new BufferedReader(new FileReader(pathDdFile));
            logger.info("Reading from " + pathDdFile);
            processDdHeader(brDd, indexesDd);
            processDdRecords(brDd, indexesDd);

            //read households and store them in the dataset
            brHh = new BufferedReader(new FileReader(pathHhFile));
            logger.info("Reading from " + pathHhFile);
            processHhHeader(brHh, indexesHh);
            processHhRecords(brHh, indexesHh, dataSet);
        } catch (IOException e) {
            e.printStackTrace();
        }

    }

    private void processDdHeader(BufferedReader brDd, Map<String, Integer> indexes) throws IOException {
        String[] header = brDd.readLine().split(REGEX);
        indexes.put("id", MitoUtil.findPositionInArray("id", header));
        indexes.put("coordX", MitoUtil.findPositionInArray("coordX", header));
        indexes.put("coordY", MitoUtil.findPositionInArray("coordY", header));
    }

    private void processDdRecords(BufferedReader brDd, Map<String, Integer> indexes) throws IOException {
        String line;
        while ((line = brDd.readLine())!= null) {

            String[] splitLine = line.split(REGEX);

            int id = Integer.parseInt(splitLine[indexes.get("id")]);
            double x = Double.parseDouble(splitLine[indexes.get("coordX")]);
            double y = Double.parseDouble(splitLine[indexes.get("coordY")]);

            Dwelling dd = new Dwelling(id, x, y);
            dwellings.put(id, dd);

        }
    }

    private void processHhHeader(BufferedReader br, Map<String, Integer>  indexes) throws IOException {
        String[] header = br.readLine().split(REGEX);
        indexes.put("id", MitoUtil.findPositionInArray("id", header));
        indexes.put("dwelling", MitoUtil.findPositionInArray("dwelling", header));
        indexes.put("autos", MitoUtil.findPositionInArray("autos", header));
        indexes.put("zone", MitoUtil.findPositionInArray("zone", header));
        indexes.put("partition", MitoUtil.findPositionInArray("partition", header));
    }


    private void processHhRecords(BufferedReader br, Map<String, Integer>  indexes, DataSet dataSet) throws IOException {

        String line;
        while ((line = br.readLine())!= null){

            String[] splitLine = line.split(REGEX);

            int id = Integer.parseInt(splitLine[indexes.get("id")]);
            int ddId = Integer.parseInt(splitLine[indexes.get("dwelling")]);

            Dwelling dd = dwellings.getOrDefault(ddId, null);

            if (dd == null){
                throw new RuntimeException("The household does not exist");
            }

            int autos = Integer.parseInt(splitLine[indexes.get("autos")]);
            int zoneId = Integer.parseInt(splitLine[indexes.get("zone")]);

            MicroscopicLocation hhLocation = new MicroscopicLocation(dd.x, dd.y);
            hhLocation.setZone(dataSet.getZones().get(zoneId));

            Household hh = new Household(id, hhLocation, autos);
            hh.setSimulated(Boolean.FALSE);

            int partition = Integer.parseInt(splitLine[indexes.get("partition")]);
            hh.setPartition(partition);

            dataSet.getHouseholds().put(id, hh);

        }

    }

    /**
     * Dwellings are just read to get the coordinates but are not used later in ABIT. We may add more information of a dwelling if needed.
     */
    private class Dwelling {

        public Dwelling(int id, double x, double y) {
            this.id = id;
            this.x = x;
            this.y = y;
        }

        int id;
        double x;
        double y;

    }
}
