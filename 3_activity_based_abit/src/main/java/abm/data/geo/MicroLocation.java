package abm.data.geo;

import org.locationtech.jts.geom.Coordinate;

public interface MicroLocation extends Location {
    Coordinate getCoordinate();
}
