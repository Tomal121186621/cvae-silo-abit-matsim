package abm.scenarios.lowEmissionZones.io;

import abm.data.DataSet;
import abm.data.geo.Zone;
import abm.properties.AbitResources;
import de.tum.bgu.msm.util.MitoUtil;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

public class LowEmissionZoneReader {

    private final DataSet dataSet;
    private final String LOW_EMISSION_ZONES_PATH = AbitResources.instance.getString("lowEmissionZones.input");
    public LowEmissionZoneReader(DataSet dataSet) {
        this.dataSet = dataSet;
    }

    public Map<Integer, Boolean> readLowEmissionZones() {
        Map<Integer, Boolean> evForbidden = new HashMap<>();
        for (Zone zoneId : dataSet.getZones().values()) {
            evForbidden.put(zoneId.getId(), false);
        }

        try {
            final Map<String, Integer> indexes = new HashMap<>();
            BufferedReader br = new BufferedReader(new FileReader(LOW_EMISSION_ZONES_PATH));
            processHeader(br, indexes);
            processRecords(br, indexes, evForbidden);
        } catch (IOException e) {
            e.printStackTrace();
        }
        return evForbidden;
    }

    private void processHeader(BufferedReader br, Map<String, Integer> indexes) throws IOException {
        String[] header = br.readLine().split(",");
        indexes.put("id", MitoUtil.findPositionInArray("id", header));
    }

    private void processRecords(BufferedReader br, Map<String, Integer> indexes, Map<Integer, Boolean> evForbidden) throws IOException {
        String line;
        while ((line = br.readLine()) != null) {
            String[] splitLine = line.split(",");
            int id = Integer.parseInt(splitLine[indexes.get("id")]);
            evForbidden.put(id, true);

        }
    }

}
