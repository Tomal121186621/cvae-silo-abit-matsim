package abm;

import abm.data.DataSet;
import abm.data.geo.MicroscopicLocation;
import abm.data.plans.*;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.data.timeOfDay.CarAvailableTimeOfWeek;
import abm.data.vehicle.Car;
import cern.colt.map.tint.OpenIntIntHashMap;

import java.lang.reflect.Array;
import java.sql.SQLOutput;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

import static abm.data.plans.Purpose.*;


public class CheckResults {

    private DataSet dataSet;



    private int numOfPeopleWithTimeConflict;
    private HashMap<Mode,Integer> legsWithWrongTravelTime = new HashMap<>();
    private int overlapCarUse;
    private int carUseInconsistency;
    private int accompanyTripInconsistency;
    private HashMap<Purpose, Integer> childTripWithoutAccompany = new HashMap<>();;
    public CheckResults(DataSet dataSet) {
        this.dataSet = dataSet;
        this.numOfPeopleWithTimeConflict = 0;
        this.overlapCarUse = 0;
        this.carUseInconsistency = 0;
        this.accompanyTripInconsistency = 0;
    }
    public void checkTimeConflict(){
        // initialize with 0
        legsWithWrongTravelTime.put(Mode.TRAIN,0);
        legsWithWrongTravelTime.put(Mode.TRAM_METRO,0);
        legsWithWrongTravelTime.put(Mode.BUS,0);
        legsWithWrongTravelTime.put(Mode.CAR_DRIVER,0);
        legsWithWrongTravelTime.put(Mode.CAR_PASSENGER,0);
        legsWithWrongTravelTime.put(Mode.BIKE,0);
        legsWithWrongTravelTime.put(Mode.WALK,0);

        for (Household household : dataSet.getHouseholds().values()){
            for (Person person : household.getPersons()){
                if (person.getPlan()!=null){
                    int[] timeConsistency = new int[10081]; // initialize the array with 0
                    HashMap<Integer, Integer> timeUse = new HashMap<>();
                    HashMap<Double, Mode> speedAndMode = new HashMap<>();
                    for (Tour tour : person.getPlan().getTours().values()){
                        for (Activity activity : tour.getActivities().values()){
                            int startTime = activity.getStartTime_min();
                            int endTime = activity.getEndTime_min()-1;
                            Purpose purpose = activity.getPurpose();
                            for (int i=startTime;i<=endTime;i++){
                                // time use purpose: 1-Work/Education, 2-Activity, 3-Home, 4-travel
                                if (i>=0 && i<=10080){
                                    timeConsistency[i]+=1;
                                }
                                if (purpose.equals(WORK) || purpose.equals(EDUCATION)){
                                    timeUse.put(i,1);
                                } else if (purpose.equals(HOME)){
                                    timeUse.put(i,3);
                                } else {
                                    timeUse.put(i,2);
                                }
                            }
                        }
                        for (Leg leg : tour.getLegs().values()){
                            int startTime = leg.getPreviousActivity().getEndTime_min();
                            int endTime = startTime+leg.getTravelTime_min()-1;
                            for (int i=startTime;i<=endTime;i++){
                                if (i>=0 && i<=10080){
                                    timeConsistency[i]+=1;
                                    timeUse.put(i,4);
                                }
                            }
                            // is the travel time reasonable for this mode
                            double speed = leg.getDistance() /  (leg.getTravelTime_min() + 1);
                            speedAndMode.put(speed, leg.getLegMode());
                        }
                    }
                    // minutes of gap time and overlap time for each person
                    int gapTime_min = 0;
                    int overlapTime_min = 0;
                    for (int i=0;i<timeConsistency.length;i++){
                        if(timeConsistency[i]==0){
                            gapTime_min++;
                        }
                        if(timeConsistency[i]>1){
                            overlapTime_min++;
                        }
                    }
                    // minutes of different time use purpose for each person
                    int mandatoryTime_min = 0;
                    int activityTime_min = 0;
                    int homeTime_min = 0;
                    int travelTime_min = 0;
                    for (int i : timeUse.keySet()){
                        if (i==1){
                            mandatoryTime_min++;
                        }
                        if (i==2){
                            activityTime_min++;
                        }
                        if (i==3){
                            homeTime_min++;
                        }
                        if (i==4){
                            travelTime_min++;
                        }
                    }
                    // number of people with conflict schedule
                    for (int i=0;i<timeConsistency.length;i++){
                        if(timeConsistency[i]>1){
                            numOfPeopleWithTimeConflict+=1;
                            break;
                        }
                    }
                    // count number of legs with unreasonable travel time


                    for (Map.Entry<Double,Mode> e : speedAndMode.entrySet()) {
//                        System.out.println("Speed: " + e.getKey());
//                        System.out.println("Mode: " + e.getValue());
                        if (e.getValue().equals(Mode.TRAIN) && e.getKey()>200){
                            legsWithWrongTravelTime.put(Mode.TRAIN, legsWithWrongTravelTime.get(Mode.TRAIN)+1);
                        }
                        if (e.getValue().equals(Mode.TRAM_METRO) && e.getKey()>200){
                            legsWithWrongTravelTime.put(Mode.TRAM_METRO, legsWithWrongTravelTime.get(Mode.TRAM_METRO)+1);
                        }
                        if (e.getValue().equals(Mode.BUS) && e.getKey()>200){
                            legsWithWrongTravelTime.put(Mode.BUS, legsWithWrongTravelTime.get(Mode.BUS)+1);
                        }
                        if (e.getValue().equals(Mode.CAR_DRIVER) && e.getKey()>200){
                            legsWithWrongTravelTime.put(Mode.CAR_DRIVER, legsWithWrongTravelTime.get(Mode.CAR_DRIVER)+1);
                        }
                        if (e.getValue().equals(Mode.CAR_PASSENGER) && e.getKey()>200){
                            legsWithWrongTravelTime.put(Mode.CAR_PASSENGER, legsWithWrongTravelTime.get(Mode.CAR_PASSENGER)+1);
                        }
                        if (e.getValue().equals(Mode.BIKE) && e.getKey()>200){
                            legsWithWrongTravelTime.put(Mode.BIKE, legsWithWrongTravelTime.get(Mode.BIKE)+1);
                        }
                        if (e.getValue().equals(Mode.WALK) && e.getKey()>200){
                            legsWithWrongTravelTime.put(Mode.WALK, legsWithWrongTravelTime.get(Mode.WALK)+1);
                        }
                    }
                }

            }
        }
    }

    public void checkVehicleUse (){
        for (Household household : dataSet.getHouseholds().values()){
            boolean HouseholdExist;
            for (Person person: household.getPersons()){
                if (person.getPlan()!=null){
                    HouseholdExist = true;
                }
            }

            if (HouseholdExist=true){
//                HashMap<Integer, int[]> carUseInHousehold= new HashMap<>();
//                for (int i=0;i<household.getVehicles().size();i++){
//                    int[] carUseTime = new int[10081];
//                    int carID = household.getVehicles().get(i).getId();
//                    for (int j=0;j<carUseTime.length;j+=15){
//                        carUseTime[j]= household.getVehicles().get(i).getCarAvailableTimeOfWeek().getInternalMap().get(j);
//                    }
//                    carUseInHousehold.put(carID, carUseTime);
//                }
                HashMap<Integer, int[]> carTourInHousehold= new HashMap<>();
                HashMap<Integer, int[]> carTourInHouseholdInterval= new HashMap<>();
                for (Person person : household.getPersons()){
                    if (person.getPlan()!=null){
                        for (Tour tour: person.getPlan().getTours().values()){
                            if (tour.getTourMode().equals(Mode.CAR_DRIVER)){
                                int carID = tour.getCar().getId();
                                int startKey = tour.getLegs().firstKey();
                                int startTime = tour.getLegs().get(startKey).getPreviousActivity().getEndTime_min();
                                int endKey = tour.getLegs().lastKey();
                                int endTime = tour.getLegs().get(endKey).getNextActivity().getStartTime_min();

                                if (!carTourInHousehold.containsKey(carID)){
                                    int[] carTourTime = new int[10081]; // initial value is 1 if the car is not being used at that time
                                    for (int i=0;i<carTourTime.length;i++){
                                        carTourTime[i]=1;
                                    }
                                    for (int j =startTime;j<=endTime;j++){
                                        if (( j >=0) && (j<=10080)){
                                            carTourTime[j]-=1;
                                        }
                                    }
                                    carTourInHousehold.put(carID, carTourTime);
                                } else {
                                    int[] currCarTourTime = carTourInHousehold.get(carID);
                                    for (int j =startTime;j<=endTime;j++){
                                        if (( j >=0) && (j<=10080)){
                                            currCarTourTime[j]-=1;
                                        }
                                    }
                                    carTourInHousehold.put(carID,currCarTourTime);
                                }

                            }
                        }
                    }
                }

//                for (int i: carTourInHousehold.keySet()){
//                    int[] carTourTimeInterval = new int[10081];
//                    for (int j=0;j<carTourInHousehold.get(i).length;j+=15){
//                        carTourTimeInterval[j] = carTourInHousehold.get(i)[j];
//                    }
//                    carTourInHouseholdInterval.put(i,carTourTimeInterval);
//                }
//                // output car use overlap and inconsistency results
//                for (int carID: carTourInHousehold.keySet()){
//                    for (int i=0;i<carTourInHousehold.get(carID).length;i+=15){
//                        if (carTourInHousehold.get(carID)[i]<0){
//                            overlapCarUse+=1;
//                            break;
//                        }
//                    }
//                }
//                for (int carID : carTourInHouseholdInterval.keySet()) {
//                    for (int i=0;i<carTourInHousehold.get(carID).length;i+=15) {
//                        if (carTourInHouseholdInterval.get(carID)[i] != carUseInHousehold.get(carID)[i]) {
//                            carUseInconsistency += 1;
//                            break;
//                        }
//                    }
//                }
            }
        }
    }

    public void checkAccompanyTrip (){
        for (Household household : dataSet.getHouseholds().values()){
            boolean HouseholdExist;
            for (Person person: household.getPersons()){
                if (person.getPlan()!=null){
                    HouseholdExist = true;
                }
            }

            if (HouseholdExist=true) {
                HashMap<ArrayList<Double>, Integer > accompanyTrip = new HashMap<ArrayList<Double>, Integer>();
                ArrayList<Double> destinationAndSchedule = new ArrayList<>();

                for (Person person : household.getPersons()){
                    if (person.getPlan()!=null){
                        for (Tour tour : person.getPlan().getTours().values()){
                            for (Leg leg : tour.getLegs().values()){
                                if (leg.getNextActivity().getPurpose().equals(ACCOMPANY)){

                                    destinationAndSchedule.add(((MicroscopicLocation)leg.getNextActivity().getLocation()).getX());
                                    destinationAndSchedule.add(((MicroscopicLocation)leg.getNextActivity().getLocation()).getY());
                                    destinationAndSchedule.add((double) leg.getPreviousActivity().getEndTime_min());
                                    destinationAndSchedule.add((double) leg.getNextActivity().getStartTime_min());
                                    if (!accompanyTrip.containsKey(destinationAndSchedule)){
                                        accompanyTrip.put(destinationAndSchedule,1);
                                    } else {
                                        accompanyTrip.put(destinationAndSchedule,accompanyTrip.get(destinationAndSchedule)+1);
                                    }
                                }
                            }
                        }
                    }
                }
                // count the number of accompany trip but without accompany in the household
                for (Integer trip : accompanyTrip.values()){
                    if(trip==1){
                        accompanyTripInconsistency++;
                    }
                }
            }
        }
    }

    public void checkChildTrip (){
        childTripWithoutAccompany.put(ACCOMPANY,0);
        childTripWithoutAccompany.put(HOME,0);
        childTripWithoutAccompany.put(EDUCATION,0);
        childTripWithoutAccompany.put(OTHER,0);
        childTripWithoutAccompany.put(RECREATION,0);
        childTripWithoutAccompany.put(SHOPPING,0);
        childTripWithoutAccompany.put(SUBTOUR,0);
        childTripWithoutAccompany.put(WORK,0);

        for (Household household : dataSet.getHouseholds().values()){
            boolean HouseholdExist;
            for (Person person: household.getPersons()){
                if (person.getPlan()!=null){
                    HouseholdExist = true;
                }
            }

            if (HouseholdExist=true) {
                HashMap<ArrayList<Double>, Integer > childTrip = new HashMap<ArrayList<Double>, Integer>();
                HashMap<ArrayList<Double>, Purpose > childTripPurpose = new HashMap<ArrayList<Double>, Purpose>();
                for (Person person : household.getPersons()){
                    if (person.getPlan()!=null && person.getAge()<=5){
                        for (Tour tour : person.getPlan().getTours().values()){
                            for (Leg leg : tour.getLegs().values()){
                                ArrayList<Double> destinationAndSchedule = new ArrayList<>();
                                destinationAndSchedule.add(((MicroscopicLocation)leg.getNextActivity().getLocation()).getX());
                                destinationAndSchedule.add(((MicroscopicLocation)leg.getNextActivity().getLocation()).getY());
                                destinationAndSchedule.add((double) leg.getPreviousActivity().getEndTime_min());
                                destinationAndSchedule.add((double) leg.getNextActivity().getStartTime_min());
                                childTrip.put(destinationAndSchedule,1);
                                childTripPurpose.put(destinationAndSchedule, leg.getNextActivity().getPurpose());

                            }
                        }
                    }
                }
                for (Person person : household.getPersons()){
                    if (person.getPlan()!=null && person.getAge()>5) {
                        for (Tour tour : person.getPlan().getTours().values()){
                            for (Leg leg : tour.getLegs().values()){
                                ArrayList<Double> currDestinationAndSchedule = new ArrayList<>();
                                double currX = ((MicroscopicLocation)leg.getNextActivity().getLocation()).getX();
                                double currY = ((MicroscopicLocation)leg.getNextActivity().getLocation()).getY();
                                double currStartTime =  leg.getPreviousActivity().getEndTime_min();
                                double currEndTime = leg.getNextActivity().getStartTime_min();
                                currDestinationAndSchedule.add(currX);
                                currDestinationAndSchedule.add(currY);
                                currDestinationAndSchedule.add(currStartTime);
                                currDestinationAndSchedule.add(currEndTime);
                                if (childTrip.keySet().contains(currDestinationAndSchedule)){
                                    childTrip.put(currDestinationAndSchedule,childTrip.get(currDestinationAndSchedule)+1);
                                }

                            }
                        }
                    }

                }
                // count the number of child trip without accompany in the household
                for (ArrayList dAndS: childTrip.keySet()){
                    if(childTrip.get(dAndS)==1){
                            childTripWithoutAccompany.put(childTripPurpose.get(dAndS),childTripWithoutAccompany.get(childTripPurpose.get(dAndS))+1);

                    }
                }
            }

        }
    }
    public int getNumOfPeopleWithTimeConflict() {
        return numOfPeopleWithTimeConflict;
    }
    public HashMap<Mode, Integer> getLegsWithWrongTravelTime() {
        return legsWithWrongTravelTime;
    }
    public int getOverlapCarUse() {
        return overlapCarUse;
    }
    public int getCarUseInconsistency() {
        return carUseInconsistency;
    }
    public int getAccompanyTripInconsistency() {
        return accompanyTripInconsistency;
    }
    public HashMap<Purpose, Integer> getChildTripWithoutAccompany() {
        return childTripWithoutAccompany;
    }
}
