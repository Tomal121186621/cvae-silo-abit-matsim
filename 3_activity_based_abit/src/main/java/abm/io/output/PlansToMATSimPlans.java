package abm.io.output;

import abm.data.DataSet;
import abm.data.geo.MicroLocation;
import abm.data.plans.*;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.data.vehicle.Car;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import org.locationtech.jts.geom.Coordinate;
import org.matsim.api.core.v01.Coord;
import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.population.Population;
import org.matsim.api.core.v01.population.PopulationWriter;
import org.matsim.core.config.Config;
import org.matsim.core.config.ConfigUtils;
import org.matsim.core.population.PopulationUtils;

import java.time.DayOfWeek;

public class PlansToMATSimPlans {


    private final DataSet dataSet;

    public PlansToMATSimPlans(DataSet dataSet) {
        this.dataSet = dataSet;
    }

    void convertPlansToMATSim(DayOfWeek dayOfWeek, Config config, String folder) {

        int midnight_min = dayOfWeek.ordinal() * 60 * 24;
        ;
        Population matsimPopulation = PopulationUtils.createPopulation(config);


        for (Household hh : dataSet.getHouseholds().values()) {

            for (Person pp : hh.getPersons()) {

                if (pp.getPlan() == null) {
                    continue;
                }

                if (AbitUtils.getRandomObject().nextDouble() > AbitResources.instance.getDouble("matsim.scale.factor", 1.0)) {
                    continue;
                }

                org.matsim.api.core.v01.population.Person matsimPerson = matsimPopulation.getFactory().createPerson(Id.createPersonId(pp.getId()));
                matsimPopulation.addPerson(matsimPerson);

                org.matsim.api.core.v01.population.Plan matsimPlan = PopulationUtils.createPlan();
                matsimPerson.addPlan(matsimPlan);
                for (Tour tour : pp.getPlan().getTours().values()) {

                    Mode tourMode = tour.getTourMode();
                    String carType = null;
                    if (tourMode.equals(Mode.CAR_DRIVER)) {
                        carType = ((Car) (tour.getCar())).getEngineType().toString();
                    }

                    //tours with the first act starting this day of week, independently of when they end, are converted to MATSim,
                    final int tourStartTime_min = tour.getLegs().get(tour.getLegs().firstKey()).getNextActivity().getStartTime_min();
                    if (tourStartTime_min > midnight_min && tourStartTime_min < midnight_min + 24 * 60) {
                        for (Leg leg : tour.getLegs().values()) {
                            if (tour.getLegs().get(tour.getLegs().firstKey()).equals(leg)) {
                                //only if this is the first leg of the tour, the previous activity is added
                                final Activity previousActivity = leg.getPreviousActivity();
                                org.matsim.api.core.v01.population.Activity previousMatsimActivity = convertActivityToMATSim(previousActivity);
                                previousMatsimActivity.setEndTime(leg.getNextActivity().getStartTime_min() * 60 - leg.getTravelTime_min() * 60 - midnight_min * 60);
                                matsimPlan.addActivity(previousMatsimActivity);

                            }

                            //matsimPlan.addLeg(PopulationUtils.createLeg(Mode.getMatsimMode(leg.getLegMode())));
                            org.matsim.api.core.v01.population.Leg firstMATSimLeg = PopulationUtils.createLeg(leg.getLegMode().toString().toLowerCase());
                            if (tourMode.equals(Mode.CAR_DRIVER)) {
                                firstMATSimLeg.getAttributes().putAttribute("vehicleType", carType);
                            }
                            matsimPlan.addLeg(firstMATSimLeg);

                            if (!tour.getLegs().get(tour.getLegs().lastKey()).equals(leg)) {
                                //only if this is not the last leg, the next activity is added
                                final Activity nextActivity = leg.getNextActivity();
                                if (nextActivity.getSubtour() != null) {
                                    //this activity has a subtour

                                    final Leg outboundLeg = nextActivity.getSubtour().getOutboundLeg();


                                    final Activity mainActivityPart1 = outboundLeg.getPreviousActivity();

                                    org.matsim.api.core.v01.population.Activity nextMatsimActivity = convertActivityToMATSim(mainActivityPart1);
                                    nextMatsimActivity.setEndTime(mainActivityPart1.getEndTime_min() * 60 - midnight_min * 60);
                                    matsimPlan.addActivity(nextMatsimActivity);

                                    // matsimPlan.addLeg(PopulationUtils.createLeg(Mode.getMatsimMode(outboundLeg.getLegMode())));
                                    org.matsim.api.core.v01.population.Leg nextMATSimLeg = PopulationUtils.createLeg(outboundLeg.getLegMode().toString().toLowerCase());
                                    if (tourMode.equals(Mode.CAR_DRIVER)) {
                                        nextMATSimLeg.getAttributes().putAttribute("vehicleType", carType);
                                    }
                                    matsimPlan.addLeg(nextMATSimLeg);


                                    final Activity subtourActivity = nextActivity.getSubtour().getSubtourActivity();

                                    nextMatsimActivity = convertActivityToMATSim(subtourActivity);
                                    nextMatsimActivity.setEndTime(subtourActivity.getEndTime_min() * 60 - midnight_min * 60);
                                    matsimPlan.addActivity(nextMatsimActivity);

                                    final Leg inboundLeg = nextActivity.getSubtour().getInboundLeg();

                                    //matsimPlan.addLeg(PopulationUtils.createLeg(Mode.getMatsimMode(outboundLeg.getLegMode())));
                                    org.matsim.api.core.v01.population.Leg nextNextLeg = PopulationUtils.createLeg(outboundLeg.getLegMode().toString().toLowerCase());
                                    if (tourMode.equals(Mode.CAR_DRIVER)) {
                                        nextNextLeg.getAttributes().putAttribute("vehicleType", carType);
                                    }

                                    matsimPlan.addLeg(nextNextLeg);

                                    final Activity mainActivityPart2 = inboundLeg.getNextActivity();

                                    nextMatsimActivity = convertActivityToMATSim(mainActivityPart2);
                                    nextMatsimActivity.setEndTime(mainActivityPart2.getEndTime_min() * 60 - midnight_min * 60);
                                    matsimPlan.addActivity(nextMatsimActivity);


                                } else {
                                    org.matsim.api.core.v01.population.Activity nextMatsimActivity = convertActivityToMATSim(nextActivity);
                                    nextMatsimActivity.setEndTime(nextActivity.getEndTime_min() * 60 - midnight_min * 60);
                                    matsimPlan.addActivity(nextMatsimActivity);
                                }


                            }

                        }
                    }
                }

                //add a last activity home until without end time

                org.matsim.api.core.v01.population.Activity lastHomeMatimActivity;
                final Coordinate coordinate = ((MicroLocation) pp.getHousehold().getLocation()).getCoordinate();
                Coord coord = new Coord(coordinate.getX(),
                        coordinate.getY());
                lastHomeMatimActivity = PopulationUtils.createActivityFromCoord(Purpose.HOME.toString().toLowerCase(), coord);
                matsimPlan.addActivity(lastHomeMatimActivity);


            }
        }

        new PopulationWriter(matsimPopulation).write(folder + "/matsimPlan_" + dayOfWeek.toString().toLowerCase() + ".xml");

    }

    private org.matsim.api.core.v01.population.Activity convertActivityToMATSim(Activity previousActivity) {
        final Coordinate coordinate = ((MicroLocation) previousActivity.getLocation()).getCoordinate();
        Coord coord = new Coord(coordinate.getX(),
                coordinate.getY());

        return PopulationUtils.createActivityFromCoord(previousActivity.getPurpose().toString().toLowerCase(), coord);
    }


    public void print(String folder) {
        for (DayOfWeek day : DayOfWeek.values()) {
            convertPlansToMATSim(day, ConfigUtils.createConfig(), folder);
        }
    }


}
