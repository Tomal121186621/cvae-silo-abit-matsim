package abm.data.pop;

import abm.data.geo.Location;

public class Job {

    final private int id;
    private int personId;
    private Person person;
    final String type;
    final private Location location;
    final private int startTime_min;
    final private int duration_min;

    public Job(int id, int personId, String type, Location location, int startTime_min, int duration_min) {
        this.id = id;
        this.personId = personId;
        this.type = type;
        this.location = location;
        this.startTime_min = startTime_min;
        this.duration_min = duration_min;
    }

    public int getId() {
        return id;
    }

    public Person getPerson() {
        return person;
    }

    public String getType() {
        return type;
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

    public void setPerson(Person person) {
        this.person = person;
        if (person.getId() != personId){
            throw new RuntimeException("Inconsistent population files! Person and Job do not match.");
        }
    }
}
