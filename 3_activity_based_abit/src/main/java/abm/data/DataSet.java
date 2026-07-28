package abm.data;

import abm.data.geo.Zone;
import abm.data.plans.Purpose;
import abm.data.pop.Job;
import abm.data.pop.School;
import abm.data.travelInformation.TravelDistances;
import abm.data.travelInformation.TravelTimes;
import abm.data.pop.Household;
import abm.data.pop.Person;
import de.tum.bgu.msm.util.matrices.IndexedDoubleMatrix2D;

import java.util.HashMap;
import java.util.Map;

public class DataSet {

    final private Map<Integer, Household> households = new HashMap<>();
    final private Map<Integer, Person> persons = new HashMap<>();
    final private Map<Integer, Job> jobs = new HashMap<>();
    final private Map<Integer, School> schools = new HashMap<>();
    private TravelTimes travelTimes;
    private TravelDistances travelDistances;
    final private Map<Integer, Zone> zones = new HashMap<>();
    final private Map<String, Map<Purpose, IndexedDoubleMatrix2D>> logsums = new HashMap<>();


    public Map<String, Map<Purpose, IndexedDoubleMatrix2D>> getLogsums() {
        return logsums;
    }

    public Map<Integer, Person> getPersons() {
        return persons;
    }

    public TravelTimes getTravelTimes() {
        return travelTimes;
    }

    public void setTravelTimes(TravelTimes travelTimes) {
        this.travelTimes = travelTimes;
    }

    public Map<Integer, Household> getHouseholds() {
        return households;
    }

    public Map<Integer, Job> getJobs() {
        return jobs;
    }

    public TravelDistances getTravelDistances() {
        return travelDistances;
    }

    public void setTravelDistances(TravelDistances travelDistances) {
        this.travelDistances = travelDistances;
    }

    public Map<Integer, Zone> getZones() {
        return zones;
    }

    public Map<Integer, School> getSchools() {
        return schools;
    }
}
