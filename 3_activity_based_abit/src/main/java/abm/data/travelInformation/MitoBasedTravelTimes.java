package abm.data.travelInformation;

import abm.data.geo.Location;
import abm.data.plans.Mode;
import de.tum.bgu.msm.data.MitoZone;


public class MitoBasedTravelTimes implements TravelTimes {

    private final de.tum.bgu.msm.data.travelTimes.TravelTimes mitoTravelTimes;

    public MitoBasedTravelTimes(de.tum.bgu.msm.data.travelTimes.TravelTimes  mitoTravelTimes) {
        this.mitoTravelTimes = mitoTravelTimes;
    }


    @Override
    public int getTravelTimeInMinutes(Location origin, Location destination, Mode mode, double time){

        de.tum.bgu.msm.data.Location mitoOrigin = new MitoZone(origin.getZoneId(), null);
        de.tum.bgu.msm.data.Location mitoDestination = new MitoZone(destination.getZoneId(), null);

        double factor = 1.;
        if (mode.equals(Mode.UNKNOWN)){
            //todo quick solution to the queries before mode selection: 80% of travel time by car;
            mode = Mode.CAR_DRIVER;
            factor = 0.8;
        }


        return (int) (factor * mitoTravelTimes.getTravelTime(mitoOrigin, mitoDestination, time, mode.toString()));
    }







}
