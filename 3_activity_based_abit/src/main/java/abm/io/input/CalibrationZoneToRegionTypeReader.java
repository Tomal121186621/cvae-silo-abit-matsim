package abm.io.input;

import abm.data.DataSet;
import abm.data.geo.*;
import abm.properties.AbitResources;
import de.tum.bgu.msm.resources.Resources;
import de.tum.bgu.msm.util.MitoUtil;
import org.apache.log4j.Logger;
import org.locationtech.jts.geom.Geometry;
import org.matsim.core.utils.gis.ShapeFileReader;
import org.opengis.feature.simple.SimpleFeature;
import java.util.Collection;
import java.util.HashMap;
import java.util.Map;
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;

public class CalibrationZoneToRegionTypeReader implements Reader {

    private static Logger logger = Logger.getLogger(CalibrationZoneToRegionTypeReader.class);
    private int zoneIndex;
    private int regionIndex;
    private final DataSet dataSet;
    private static Map<Integer, String> zoneToRegionMap = new HashMap<>();

    public CalibrationZoneToRegionTypeReader(DataSet dataSet) {
        this.dataSet = dataSet;
    }

    private void processHeader(String[] header) {
        zoneIndex = MitoUtil.findPositionInArray("zone", header);
        regionIndex = MitoUtil.findPositionInArray("calibrationRegion", header);
    }

    private void processRecord(String[] record) {
        int zone = Integer.parseInt(record[zoneIndex]);
        String region = record[regionIndex];

        zoneToRegionMap.put(zone, region);
    }

    @Override
    public void read() {
        String calibrationRegionFile = AbitResources.instance.getString("calibration.region.mapping");
        try (BufferedReader br = new BufferedReader(new FileReader(calibrationRegionFile))) {
            String line;
            boolean headerProcessed = false;
            while ((line = br.readLine()) != null) {
                String[] record = line.split(",");
                if (!headerProcessed) {
                    processHeader(record);
                    headerProcessed = true;
                } else {
                    processRecord(record);
                }
            }
        } catch (IOException e) {
            logger.error("Error reading calibrationRegion.csv", e);
        }

        logger.info("Loaded " + zoneToRegionMap.size() + " zone-to-region mappings.");
    }

    public static Map<Integer, String> getZoneToRegionMap() {
        return zoneToRegionMap;
    }

    // Utility method to get the region for a given zone
    public static String getRegionForZone(int zoneId) {
        return zoneToRegionMap.getOrDefault(zoneId, "nonMuc"); // Default to "unknown" if not found
    }
}