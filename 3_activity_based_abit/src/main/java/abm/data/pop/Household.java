package abm.data.pop;

import abm.data.geo.Location;
import abm.data.vehicle.Car;
import abm.data.vehicle.CarType;
import abm.data.vehicle.Vehicle;
import abm.data.vehicle.VehicleUtil;


import java.util.ArrayList;
import java.util.List;

public class Household {

    private int id;
    private List<Person> persons;
    private Location location;
    private final int numberOfCars;
    private List<Vehicle> vehicles = new ArrayList<>();
    private EconomicStatus economicStatus;

    public Boolean getSimulated() {
        return simulated;
    }

    public void setSimulated(Boolean simulated) {
        this.simulated = simulated;
    }

    private Boolean simulated;



    private int partition;


    public Household(int id, Location location, int numberOfCars) {
        this.id = id;
        this.numberOfCars = numberOfCars;
        this.persons = new ArrayList<>();
        this.location = location;
    }

    public int getId() {
        return id;
    }

    public List<Person> getPersons() {
        return persons;
    }

    public Location getLocation() {
        return location;
    }

    public void setEconomicStatus(EconomicStatus economicStatus) {
        this.economicStatus = economicStatus;
    }

    public EconomicStatus getEconomicStatus() {
        return this.economicStatus;
    }

    public int getNumberOfCars() {
        return numberOfCars;
    }

    public List<Vehicle> getVehicles() {
        return vehicles;
    }

    public int getPartition() {
        return partition;
    }

    public void setPartition(int partition) {
        this.partition = partition;
    }

}
