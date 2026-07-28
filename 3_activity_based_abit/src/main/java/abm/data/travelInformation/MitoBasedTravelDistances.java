package abm.data.travelInformation;

import abm.data.geo.Location;
import abm.data.plans.Mode;
import de.tum.bgu.msm.data.MitoZone;


public class MitoBasedTravelDistances implements TravelDistances {

    private final de.tum.bgu.msm.data.travelTimes.TravelTimes mitoTravelTimes;

    public MitoBasedTravelDistances(de.tum.bgu.msm.data.travelTimes.TravelTimes mitoTravelTimes) {
        this.mitoTravelTimes = mitoTravelTimes;
    }



    @Override
    public int getTravelDistanceInMeters(Location origin, Location destination, Mode mode, double time) {

        de.tum.bgu.msm.data.Location mitoOrigin = new MitoZone(origin.getZoneId(), null);
        de.tum.bgu.msm.data.Location mitoDestination = new MitoZone(destination.getZoneId(), null);

        return (int) mitoTravelTimes.getTravelTime(mitoOrigin, mitoDestination, time, mode.toString());
    }
}
