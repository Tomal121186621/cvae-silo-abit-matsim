package abm.data.geo;

import de.tum.bgu.msm.data.Id;
import de.tum.bgu.msm.utils.SeededRandomPointsBuilder;
import org.locationtech.jts.geom.Coordinate;
import org.locationtech.jts.geom.Geometry;
import org.locationtech.jts.geom.GeometryFactory;
import org.locationtech.jts.geom.Point;
import org.locationtech.jts.shape.random.RandomPointsBuilder;
import org.matsim.core.utils.geometry.geotools.MGC;
import org.matsim.utils.objectattributes.attributable.Attributes;

import java.util.Optional;
import java.util.Random;

public class Zone implements Location, Id {

    private int id;
    private BBSRType BBSRType;
    private RegioStaR2 regioStaR2Type;
    private RegioStaR7 regioStaR7Type;
    private RegioStaRGem5 regioStaRGem5Type;
    private Geometry geometry;
    private String name;

    private double areaKm2;

    private long distToRail_meter;
    private final Attributes attributes = new Attributes();
    public double getDistToRail_meter() {
        return distToRail_meter;
    }

    public void setDistToRail_meter(long distToRail_meter) {
        this.distToRail_meter = distToRail_meter;
    }

    public Zone(int id) {
        this.id = id;
    }

    public void setId(int id) {
        this.id = id;
    }

    @Override
    public int getZoneId() {
        return id;
    }

    public BBSRType getBBSRType() {
        return BBSRType;
    }

    public void setAreaType1(BBSRType BBSRType) {
        this.BBSRType = BBSRType;
    }

    public Geometry getGeometry() {
        return geometry;
    }

    public void setGeometry(Geometry geometry) {
        this.geometry = geometry;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public RegioStaR7 getRegioStaR7Type() {
        return regioStaR7Type;
    }

    public RegioStaR2 getRegioStaR2Type() {
        return regioStaR2Type;
    }

    public RegioStaRGem5 getRegioStaRGem5Type() {
        return regioStaRGem5Type;
    }

    public void setRegioStaR2Type(RegioStaR2 regioStaR2Type) {
        this.regioStaR2Type = regioStaR2Type;
    }

    public void setRegioStaR7Type(RegioStaR7 regioStaR7Type) {
        this.regioStaR7Type = regioStaR7Type;
    }

    public void setRegioStaRGem5Type(RegioStaRGem5 regioStaRGem5Type) {
        this.regioStaRGem5Type = regioStaRGem5Type;
    }

    @Override
    public int getId() {
        return id;
    }

    public Coordinate getRandomCoordinate(Random random) {
        RandomPointsBuilder randomPointsBuilder = new SeededRandomPointsBuilder(new GeometryFactory(), random);
        randomPointsBuilder.setNumPoints(1);
        randomPointsBuilder.setExtent(geometry);
        Coordinate coordinate = randomPointsBuilder.getGeometry().getCoordinates()[0];
        Point p = MGC.coordinate2Point(coordinate);
        return new Coordinate(p.getX(), p.getY());
    }

    public Attributes getAttributes() {
        return attributes;
    }

    public Optional<Object> getAttribute(String key) {
        return Optional.ofNullable(attributes.getAttribute(key));
    }

    public void setAttribute(String key, Object value) {
        attributes.putAttribute(key, value);
    }

    public double getAreaKm2() {
        return areaKm2;
    }

    public void setAreaKm2(double areaKm2) {
        this.areaKm2 = areaKm2;
    }
}
