package abm.data.vehicle;

import abm.data.timeOfDay.CarAvailableTimeOfWeek;

public interface Vehicle {

    int getId();

    VehicleType getType();

    int getAge();

    CarAvailableTimeOfWeek getCarAvailableTimeOfWeek();


}
