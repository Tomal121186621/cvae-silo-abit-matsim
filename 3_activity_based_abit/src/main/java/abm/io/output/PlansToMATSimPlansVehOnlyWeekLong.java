package abm.io.output;

import abm.data.DataSet;
import abm.data.geo.MicroLocation;
import abm.data.plans.Activity;
import abm.data.plans.Leg;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.data.vehicle.Car;
import abm.data.vehicle.Vehicle;
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
import java.util.SortedMap;
import java.util.TreeMap;

public class PlansToMATSimPlansVehOnlyWeekLong {


    private final DataSet dataSet;

    public PlansToMATSimPlansVehOnlyWeekLong(DataSet dataSet) {
        this.dataSet = dataSet;
    }

    void convertPlansToMATSim(Config config, String folder) {

        Population matsimPopulation = PopulationUtils.createPopulation(config);

        for (Household hh : dataSet.getHouseholds().values()) {

            for (Vehicle vehicle : hh.getVehicles()) {

                boolean hasPlan = false;
                String carType = ((Car) (vehicle)).getEngineType().toString();

                int vehId = vehicle.getId();
                Id<org.matsim.api.core.v01.population.Person> idVehicle = Id.createPersonId("veh_" + vehicle.getId());

                org.matsim.api.core.v01.population.Person matsimPerson = matsimPopulation.getFactory().createPerson(Id.createPersonId(idVehicle));
                matsimPopulation.addPerson(matsimPerson);
                org.matsim.api.core.v01.population.Plan matsimPlan = PopulationUtils.createPlan();
                matsimPerson.addPlan(matsimPlan);

                SortedMap<Integer, Leg> legSortedMap = new TreeMap<>();

                for (Person pp : hh.getPersons()) {

                    if (pp.getPlan() == null) {
                        continue;
                    }

                    if (AbitUtils.getRandomObject().nextDouble() > AbitResources.instance.getDouble("matsim.scale.factor", 1.0)) {
                        continue;
                    }

                    for (Tour tour : pp.getPlan().getTours().values()) {
                        if (tour.getCar() != null && tour.getCar().getId() == vehId) {

                            hasPlan = true;
                            //tours with the first act starting this day of week, independently of when they end, are converted to MATSim,

                            for (Leg leg : tour.getLegs().values()) {
                                if (tour.getLegs().get(tour.getLegs().firstKey()).equals(leg)) {
                                    legSortedMap.put(leg.getNextActivity().getStartTime_min() * 60 - leg.getTravelTime_min() * 60, leg);
                                }
                                if (tour.getLegs().get(tour.getLegs().lastKey()).equals(leg)) {
                                    legSortedMap.put(leg.getPreviousActivity().getEndTime_min() * 60, leg);
                                }
                            }

                            if (tour.getMainActivity().getSubtour() != null) {
                                legSortedMap.put(tour.getMainActivity().getSubtour().getOutboundLeg().getPreviousActivity().getEndTime_min() * 60,
                                        tour.getMainActivity().getSubtour().getOutboundLeg());
                                legSortedMap.put(tour.getMainActivity().getSubtour().getInboundLeg().getPreviousActivity().getEndTime_min() * 60,
                                        tour.getMainActivity().getSubtour().getInboundLeg());
                            }
                        }
                    }
                }

                for (Leg leg : legSortedMap.values()) {
                    final Activity previousActivity = leg.getPreviousActivity();
                    org.matsim.api.core.v01.population.Activity previousMatsimActivity = convertActivityToMATSim(previousActivity);
                    if (leg.getPreviousActivity().getPurpose().equals(Purpose.HOME)) {
                        previousMatsimActivity.setEndTime(leg.getNextActivity().getStartTime_min() * 60 - leg.getTravelTime_min() * 60);
                    } else {
                        previousMatsimActivity.setEndTime(leg.getPreviousActivity().getEndTime_min() * 60);
                    }
                    matsimPlan.addActivity(previousMatsimActivity);
                    matsimPlan.addLeg(PopulationUtils.createLeg("Car" + "_" + carType));
                }
                if (!hasPlan) {
                    matsimPopulation.removePerson(idVehicle);
                } else {
                    org.matsim.api.core.v01.population.Activity lastHomeMatimActivity;
                    final Coordinate coordinate = ((MicroLocation) hh.getLocation()).getCoordinate();
                    Coord coord = new Coord(coordinate.getX(), coordinate.getY());
                    lastHomeMatimActivity = PopulationUtils.createActivityFromCoord(Purpose.HOME.toString().toLowerCase(), coord);
                    matsimPlan.addActivity(lastHomeMatimActivity);
                }
            }
        }
        new PopulationWriter(matsimPopulation).write(folder + "/matsimVehiclePlan_week.xml");
    }

    private org.matsim.api.core.v01.population.Activity convertActivityToMATSim(Activity previousActivity) {
        final Coordinate coordinate = ((MicroLocation) previousActivity.getLocation()).getCoordinate();
        Coord coord = new Coord(coordinate.getX(),
                coordinate.getY());
        return PopulationUtils.createActivityFromCoord(previousActivity.getPurpose().toString().toLowerCase(), coord);
    }

    public void print(String folder) {

        convertPlansToMATSim(ConfigUtils.createConfig(), folder);

    }

}
