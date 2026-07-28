package abm.data.plans;

import abm.data.geo.MicroscopicLocation;
import abm.data.vehicle.Vehicle;
import abm.utils.AbitUtils;

import java.util.Objects;
import java.util.SortedMap;
import java.util.TreeMap;

public class Tour {
    private final int id;
    private final SortedMap<Integer, Activity> activities;
    private final SortedMap<Integer, Leg> legs;
    private final Activity mainActivity;
    private final SortedMap<Integer, Tour> subtours;
    Mode tourMode;
    private Vehicle car = null;


    public Tour(Activity mainActivity, int id) {
        this.mainActivity = mainActivity;
        activities = new TreeMap<>();
        activities.put(mainActivity.getStartTime_min(), mainActivity);
        legs = new TreeMap<>();
        subtours = new TreeMap<>();
        this.id = id;
    }

    public SortedMap<Integer, Leg> getLegs() {
        return legs;
    }

    public SortedMap<Integer, Activity> getActivities() {
        return activities;
    }

    public SortedMap<Integer, Tour> getSubtours() {
        return subtours;
    }

    public Activity getMainActivity() {
        return mainActivity;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Tour tour = (Tour) o;
        return Objects.equals(activities, tour.activities) &&
                Objects.equals(legs, tour.legs) &&
                Objects.equals(mainActivity, tour.mainActivity) &&
                Objects.equals(subtours, tour.subtours) &&
                tourMode == tour.tourMode;
    }

    @Override
    public int hashCode() {
        return Objects.hash(activities, legs, mainActivity, subtours, tourMode);
    }

    public Vehicle getCar() {
        return car;
    }

    public void setCar(Vehicle car) {
        this.car = car;
    }

    public int getId() {
        return id;
    }

    public Mode getTourMode() {
        return tourMode;
    }

    public void setTourMode(Mode tourMode) {
        this.tourMode = tourMode;
    }

    @Override
    public String toString() {
        StringBuilder builder = new StringBuilder();
        builder.append(mainActivity.getPerson().getId()).append(AbitUtils.SEPARATOR);
        builder.append(mainActivity.getPerson().getHabitualMode().toString()).append(AbitUtils.SEPARATOR);
        builder.append(id).append(AbitUtils.SEPARATOR);
        builder.append(mainActivity.getDayOfWeek().getValue()).append(AbitUtils.SEPARATOR);
        builder.append(legs.firstKey()).append(AbitUtils.SEPARATOR);
        builder.append(legs.lastKey() + legs.get(legs.lastKey()).getTravelTime_min()).append(AbitUtils.SEPARATOR);
        builder.append(tourMode == null? "null" : tourMode.toString()).append(AbitUtils.SEPARATOR);
        builder.append(mainActivity.getPurpose().toString()).append(AbitUtils.SEPARATOR);
        builder.append(mainActivity.getPerson().getHousehold().getId()).append(AbitUtils.SEPARATOR);
        builder.append(car == null? -1 : car.getId()).append(AbitUtils.SEPARATOR);
        builder.append(activities.size()).append(AbitUtils.SEPARATOR);
        builder.append(legs.size()).append(AbitUtils.SEPARATOR);
        builder.append(subtours.size());
        return builder.toString();
    }


    public static String getHeader() {
        StringBuilder builder = new StringBuilder();
        builder.append("person_id").append(AbitUtils.SEPARATOR);
        builder.append("habitual_mode").append(AbitUtils.SEPARATOR);
        builder.append("tour_id").append(AbitUtils.SEPARATOR);
        builder.append("day").append(AbitUtils.SEPARATOR);
        builder.append("tour_start_time_min").append(AbitUtils.SEPARATOR);
        builder.append("tour_end_time_min").append(AbitUtils.SEPARATOR);
        builder.append("tour_mode").append(AbitUtils.SEPARATOR);
        builder.append("main_activity_purpose").append(AbitUtils.SEPARATOR);
        builder.append("household_id").append(AbitUtils.SEPARATOR);
        builder.append("vehicle_id").append(AbitUtils.SEPARATOR);
        builder.append("num_activity").append(AbitUtils.SEPARATOR);
        builder.append("num_legs").append(AbitUtils.SEPARATOR);
        builder.append("num_subtours");
        return builder.toString();
    }
}
