package abm.data.plans;


import abm.utils.AbitUtils;
import abm.data.geo.Location;
import abm.data.geo.MicroscopicLocation;
import abm.data.pop.Person;

import java.time.DayOfWeek;

public class Activity implements Comparable<Activity> {

    private Person person;
    private Tour tour;
    private Purpose purpose;
    private DayOfWeek dayOfWeek;
    private int startTime_min;
    private int endTime_min;
    private DiscretionaryActivityType discretionaryActivityType;
    private Location location;

    public Subtour getSubtour() {
        return subtour;
    }

    public void setSubtour(Subtour subtour) {
        this.subtour = subtour;
    }

    private Subtour subtour;

    public Activity(Person person, Purpose purpose) {
        this.purpose = purpose;
        this.person = person;
    }

    public Purpose getPurpose() {
        return purpose;
    }

    public int getStartTime_min() {
        return startTime_min;
    }

    public int getEndTime_min() {
        return endTime_min;
    }

    public Location getLocation() {
        return location;
    }

    public void setStartTime_min(int startTime_min) {
        this.startTime_min = startTime_min;
    }

    public void setEndTime_min(int endTime_min) {
        this.endTime_min = endTime_min;
    }

    public int getDuration() {
        return endTime_min - startTime_min;
    }

    public void setLocation(Location location) {
        this.location = location;
    }

    @Override
    public int compareTo(Activity activity) {
        if (activity.getStartTime_min() < this.getStartTime_min()) {
            return 1;
        } else if (activity.getStartTime_min() == this.getStartTime_min()) {
            return 0;
        } else {
            return -1;
        }
    }

    @Override
    public String toString() {
        StringBuilder builder = new StringBuilder();
        builder.append(person.getId()).append(AbitUtils.SEPARATOR);
        builder.append(person.getHousehold().getId()).append(AbitUtils.SEPARATOR);
        builder.append(dayOfWeek.getValue()).append(AbitUtils.SEPARATOR);
        builder.append(startTime_min).append(AbitUtils.SEPARATOR);
        builder.append(endTime_min).append(AbitUtils.SEPARATOR);
        builder.append(purpose).append(AbitUtils.SEPARATOR);
        builder.append(location.getZoneId()).append(AbitUtils.SEPARATOR);

        if (location instanceof MicroscopicLocation) {
            final MicroscopicLocation microscopicLocation = (MicroscopicLocation) location;
            builder.append(microscopicLocation.getX()).append(AbitUtils.SEPARATOR);
            builder.append(microscopicLocation.getY()).append(AbitUtils.SEPARATOR);
        } else {
            builder.append(-1).append(AbitUtils.SEPARATOR);
            builder.append(-1).append(AbitUtils.SEPARATOR);
        }

        builder.append(location.getZoneId()).append(AbitUtils.SEPARATOR);

        if (discretionaryActivityType != null) {
            builder.append(discretionaryActivityType);
        } else {
            builder.append("MANDATORY");
        }


        if (subtour != null){
            builder.append("\n");
            builder.append(subtour.getSubtourActivity());
        }


        return builder.toString();
    }


    public static String getHeader() {
        StringBuilder builder = new StringBuilder();
        builder.append("person_id").append(AbitUtils.SEPARATOR);
        builder.append("household_id").append(AbitUtils.SEPARATOR);
        builder.append("day").append(AbitUtils.SEPARATOR);
        builder.append("start_time_min").append(AbitUtils.SEPARATOR);
        builder.append("end_time_min").append(AbitUtils.SEPARATOR);
        builder.append("purpose").append(AbitUtils.SEPARATOR);
        builder.append("zone_id").append(AbitUtils.SEPARATOR);
        builder.append("x").append(AbitUtils.SEPARATOR);
        builder.append("y").append(AbitUtils.SEPARATOR);
        builder.append("zone").append(AbitUtils.SEPARATOR);
        builder.append("activity_type");
        return builder.toString();
    }

    public DayOfWeek getDayOfWeek() {
        return dayOfWeek;
    }

    public void setDayOfWeek(DayOfWeek dayOfWeek) {
        this.dayOfWeek = dayOfWeek;
    }

    public DiscretionaryActivityType getDiscretionaryActivityType() {
        return discretionaryActivityType;
    }

    public void setDiscretionaryActivityType(DiscretionaryActivityType discretionaryActivityType) {
        this.discretionaryActivityType = discretionaryActivityType;
    }

    public void setTour(Tour tour) {
        this.tour = tour;
    }

    public Person getPerson() {
        return person;
    }

}
