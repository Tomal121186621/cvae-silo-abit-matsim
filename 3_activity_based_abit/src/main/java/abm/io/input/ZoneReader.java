package abm.io.input;

import abm.data.DataSet;
import abm.data.geo.*;
import abm.properties.AbitResources;
import org.apache.log4j.Logger;
import org.locationtech.jts.geom.Geometry;
import org.matsim.core.utils.gis.ShapeFileReader;
import org.opengis.feature.simple.SimpleFeature;

import java.util.Collection;


public class ZoneReader implements Reader {

    private static Logger logger = Logger.getLogger(ZoneReader.class);
    private String zoneIdField = "id";
    private String zoneNameField = "AGS";
    private String bbsrTypeField = "BBSR_type";
    private String regioStaR2TypeField = "RegioStaR2";
    private String regioStaRGem5TypeField = "RegStaRGe5";
    private String regioStaR7TypeField = "RegioStaR7";
    private String distToRailMeter = "dist2Trans";

    private String areakm2 = "area_km2";

    private final DataSet dataSet;


    public ZoneReader(DataSet dataSet) {
        this.dataSet = dataSet;
    }


    @Override
    public void read() {

        String zoneShapeFilePath = AbitResources.instance.getString("zones.shp");

        int zoneCounter = 0;

        final Collection<SimpleFeature> allFeatures = ShapeFileReader.getAllFeatures(zoneShapeFilePath);
        for (SimpleFeature feature : allFeatures) {
            int zoneId = Integer.parseInt(feature.getAttribute(zoneIdField).toString());

            Zone zone = new Zone(zoneId);

            zone.setGeometry((Geometry) feature.getDefaultGeometry());
            final Object name = feature.getAttribute(zoneNameField);
            if (name != null) {
                zone.setName(name.toString());
            }
            final Object areaType = feature.getAttribute(bbsrTypeField);
            if (areaType != null) {
                zone.setAreaType1(BBSRType.valueOf(Integer.parseInt(areaType.toString())));
            }

            final Object regioStaR2Type = feature.getAttribute(regioStaR2TypeField);
            if (regioStaR2Type != null) {
                zone.setRegioStaR2Type(RegioStaR2.valueOf(Integer.parseInt(regioStaR2Type.toString())));
            }

            final Object regioStaRGem5Type = feature.getAttribute(regioStaRGem5TypeField);
            if (regioStaRGem5Type != null) {
                zone.setRegioStaRGem5Type(RegioStaRGem5.valueOf(Integer.parseInt(regioStaRGem5Type.toString())));
            }

            final Object regioStaR7Type = feature.getAttribute(regioStaR7TypeField);
            if (regioStaR7Type != null) {
                zone.setRegioStaR7Type(RegioStaR7.valueOf(Integer.parseInt(regioStaR7Type.toString())));
            }

            final Object distToRail_meter = feature.getAttribute(distToRailMeter);
            if (distToRail_meter != null) {
                zone.setDistToRail_meter((Long) distToRail_meter);
            } else {
                zone.setDistToRail_meter((long) Double.POSITIVE_INFINITY);
            }

            final Object surfaceArea_km2 = feature.getAttribute(areakm2);
            if (surfaceArea_km2 != null) {
                zone.setAreaKm2((double) surfaceArea_km2);
            } else {
                zone.setAreaKm2(Double.POSITIVE_INFINITY);
            }

            dataSet.getZones().put(zoneId, zone);
            zoneCounter++;

        }
        logger.info("Loaded " + zoneCounter + " zones.");


    }
}
