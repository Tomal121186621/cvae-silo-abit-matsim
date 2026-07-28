package abm.data.travelInformation;

import abm.data.geo.Location;
import abm.data.plans.Mode;

public interface TravelDistances {
    int getTravelDistanceInMeters(Location origin, Location destination, Mode mode, double time);
}
