package abm.data.pop;

import abm.data.geo.Location;

public class School {

    final private int id;
    final String type;
    final int capacity;
    final int occupancy;
    final private Location location;
    final private int startTime_min;
    final private int duration_min;


    public School(int id, String type, int capacity, int occupancy, Location location, int startTime_min, int duration_min) {
        this.id = id;
        this.type = type;
        this.capacity = capacity;
        this.occupancy = occupancy;
        this.location = location;
        this.startTime_min = startTime_min;
        this.duration_min = duration_min;
    }

    public int getId() {
        return id;
    }

    public int getCapacity() {
        return capacity;
    }

    public Location getLocation() {
        return location;
    }

    public int getStartTime_min() {
        return startTime_min;
    }

    public int getDuration_min() {
        return duration_min;
    }
}
