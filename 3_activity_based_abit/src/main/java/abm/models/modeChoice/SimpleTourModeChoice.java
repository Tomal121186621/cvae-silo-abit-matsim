package abm.models.modeChoice;

import abm.data.DataSet;
import abm.data.plans.Leg;
import abm.data.plans.Mode;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.properties.InternalProperties;
import abm.utils.AbitUtils;

public class SimpleTourModeChoice implements TourModeChoice {

    private final DataSet dataSet;

    public SimpleTourModeChoice(DataSet dataSet) {
        this.dataSet = dataSet;
    }

    @Override
    public void chooseMode(Person person, Tour tour, Purpose purpose) {

    }

    @Override
    public Mode chooseMode(Person person, Tour tour, Purpose purpose, Boolean carAvailable) {
        return null;
    }

    @Override
    public void checkCarAvailabilityAndChooseMode(Household household, Person person, Tour tour, Purpose purpose) {

    }

    @Override
    public void chooseMode(Person person, Tour tour) {

        double distance = 0;

        for (Leg leg : tour.getLegs().values()) {
            distance += dataSet.getTravelDistances().getTravelDistanceInMeters(leg.getPreviousActivity().getLocation(),
                    leg.getNextActivity().getLocation(), Mode.UNKNOWN, InternalProperties.PEAK_HOUR_MIN);
        }

        double randomNumber = AbitUtils.getRandomObject().nextDouble();

        Mode mode;
        if (distance < 1000){
            if (randomNumber < 0.5){
                mode = Mode.WALK;
            } else {
                mode = Mode.BIKE;
            }
        } else if (distance < 3000){
            if (randomNumber < 0.1){
                mode = Mode.WALK;
            } else if (randomNumber < 0.4){
                mode = Mode.BIKE;
            } else  if (randomNumber < 0.7){
                mode = Mode.CAR_DRIVER;
            } else  if (randomNumber < 0.8){
                mode = Mode.BUS;
            } else  if (randomNumber < 0.9){
                mode = Mode.TRAM_METRO;
            }else {
                mode = Mode.TRAIN;
            }
        } else if (distance < 5000){
            if (randomNumber < 0.3){
                mode = Mode.BIKE;
            } else  if (randomNumber < 0.6){
                mode = Mode.CAR_DRIVER;
            } else  if (randomNumber < 0.75){
                mode = Mode.BUS;
            } else  if (randomNumber < 0.85){
                mode = Mode.TRAM_METRO;
            } else {
                mode = Mode.TRAIN;
            }

        } else if (distance < 10000){
            if (randomNumber < 0.1){
                mode = Mode.BIKE;
            } else  if (randomNumber < 0.6){
                mode = Mode.CAR_DRIVER;
            } else  if (randomNumber < 0.75){
                mode = Mode.BUS;
            } else  if (randomNumber < 0.85){
                mode = Mode.TRAM_METRO;
            } else {
                mode = Mode.TRAIN;
            }

        } else {
            if (randomNumber < 0.05){
                mode = Mode.BIKE;
            } else  if (randomNumber < 0.8){
                mode = Mode.CAR_DRIVER;
            } else  if (randomNumber < 0.85){
                mode = Mode.BUS;
            } else  if (randomNumber < 0.90){
                mode = Mode.TRAM_METRO;
            } else {
                mode = Mode.TRAIN;
            }

        }

        for (Leg leg : tour.getLegs().values()) {
            leg.setLegMode(mode);
        }


    }
}
