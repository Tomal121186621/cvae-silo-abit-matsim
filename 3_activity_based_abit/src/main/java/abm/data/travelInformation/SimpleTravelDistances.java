package abm.data.travelInformation;

import abm.data.geo.Location;
import abm.data.geo.MicroscopicLocation;
import abm.data.plans.Mode;

public class SimpleTravelDistances implements TravelDistances {
    @Override
    public int getTravelDistanceInMeters(Location origin, Location destination, Mode mode, double time) {

        double distance_m = Math.abs(((MicroscopicLocation) origin).getX() - ((MicroscopicLocation)destination).getX()) +
                Math.abs(((MicroscopicLocation) origin).getY() - ((MicroscopicLocation)destination).getY());

        return (int) distance_m;
    }
}
