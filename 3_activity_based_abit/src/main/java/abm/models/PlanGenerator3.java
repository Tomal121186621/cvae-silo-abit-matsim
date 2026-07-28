package abm.models;

import abm.data.DataSet;
import abm.data.geo.Location;
import abm.data.plans.*;
import abm.data.pop.*;
import abm.io.input.BikeOwnershipReader;
import abm.models.activityGeneration.frequency.FrequencyGenerator;
import abm.models.activityGeneration.frequency.SubtourGenerator;
import abm.models.activityGeneration.splitByType.SplitByType;
import abm.models.activityGeneration.splitByType.SplitStopType;
import abm.models.activityGeneration.time.*;
import abm.models.destinationChoice.DestinationChoice;
import abm.models.destinationChoice.SubtourDestinationChoice;
import abm.models.modeChoice.HabitualModeChoice;
import abm.models.modeChoice.SubtourModeChoice;
import abm.models.modeChoice.TourModeChoice;
import abm.utils.PlanTools;
import de.tum.bgu.msm.data.person.Occupation;
import org.apache.log4j.Logger;
import umontreal.ssj.probdist.NegativeBinomialDist;

import java.time.DayOfWeek;
import java.util.*;
import java.util.concurrent.Callable;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Collectors;

public class PlanGenerator3 implements Callable {

    private static Logger logger = Logger.getLogger(PlanGenerator3.class);

    private BikeOwnershipReader bikeOwnershipModel;
    private HabitualModeChoice habitualModeChoice;
    private Map<Purpose, FrequencyGenerator> frequencyGenerators;
    private DestinationChoice destinationChoice;
    private TourModeChoice tourModeChoice;
    private DayOfWeekMandatoryAssignment dayOfWeekMandatoryAssignment;
    private DayOfWeekDiscretionaryAssignment dayOfWeekDiscretionaryAssignment;
    private TimeAssignment timeAssignment;
    private SplitByType splitByType;
    private SplitStopType stopSplitType;

    private SubtourGenerator subtourGenerator;
    private SubtourTimeAssignment subtourTimeAssignment;
    private SubtourDestinationChoice subtourDestinationChoice;


    PlanTools planTools;

    private AtomicInteger counter;
    private AtomicInteger stopWithoutTypecounter;

    private final DataSet dataSet;
    private List<Person> persons;
    private List<Household> households;
    private final int thread;
    private final SubtourModeChoice subtourModeChoice;

    private final int TRIALS_RESCHEDULING = -1;


    public PlanGenerator3(DataSet dataSet, ModelSetup modelSetup, int thread) {
        this.dataSet = dataSet;
        this.planTools = new PlanTools(dataSet.getTravelTimes());
        this.thread = thread;

        counter = new AtomicInteger(0);
        stopWithoutTypecounter = new AtomicInteger(0);

        this.stopSplitType = modelSetup.getStopSplitType();
        this.splitByType = modelSetup.getSplitByType();
        this.timeAssignment = modelSetup.getTimeAssignment();
        this.dayOfWeekMandatoryAssignment = modelSetup.getDayOfWeekMandatoryAssignment();
        this.dayOfWeekDiscretionaryAssignment = modelSetup.getDayOfWeekDiscretionaryAssignment();
        this.destinationChoice = modelSetup.getDestinationChoice();
        this.tourModeChoice = modelSetup.getTourModeChoice();
        this.habitualModeChoice = modelSetup.getHabitualModeChoice();
        this.frequencyGenerators = modelSetup.getFrequencyGenerator();
        this.subtourGenerator = modelSetup.getSubtourGenerator();
        this.subtourTimeAssignment = modelSetup.getSubtourTimeAssignment();
        this.subtourDestinationChoice = modelSetup.getSubtourDestinationChoice();
        this.subtourModeChoice = modelSetup.getSubtourModeChoice();
        this.bikeOwnershipModel = ((ModelSetupMuc)modelSetup).getBikeOwnershipReader();

    }

    public Callable setPersons(List<Person> persons) {
        this.persons = persons;
        return this;
    }

    public Callable setHouseholds(List<Household> households) {
        this.households = households;
        return this;
    }


    private void createPlanForOneHousehold(Household household) {

        for (Person person : household.getPersons()) {
            createPlanForOnePerson(person);
        }

        //Start: Vehicle assignment and mode choice
        if (household.getNumberOfCars() > 0) {
            for (Purpose purpose : Purpose.getSortedPurposes()) {
                if (purpose.equals(Purpose.WORK)) {
                    //Step 1: loop over all workers in the household, check car and transit travel time ratio
                    // car/pt ratio the smaller (more poor pt accessibility compared to car), then higher preference to use car
                    List<Person> workers = household.getPersons().stream().filter(pp -> pp.hasWorkActivity()).collect(Collectors.toList());
                    Map<Person, Double> carUsePreference = new HashMap<>();
                    for (Person person : workers) {
                        Location jobLocation;
                        double startTime;
                        if (person.getJob() != null) {
                            jobLocation = person.getJob().getLocation();
                            startTime = person.getJob().getStartTime_min();
                        } else {
                            //job location for non-employed person but has a work tour, e.g. student go for interview or internship
                            Activity workActivity = person.getPlan().getTours().values().stream().filter(tour -> tour.getMainActivity().getPurpose().equals(Purpose.WORK)).collect(Collectors.toList()).get(0).getMainActivity();
                            jobLocation = workActivity.getLocation();
                            startTime = workActivity.getStartTime_min();
                        }

                        int carTravelTime = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), jobLocation, Mode.CAR_DRIVER, startTime);
                        int transitTravelTime = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), jobLocation, Mode.TRAIN, startTime);
                        double carPtRatio = carTravelTime / (double) transitTravelTime;
                        carUsePreference.put(person, carPtRatio);
                    }

                    List<Map.Entry<Person, Double>> sortedPreference = new ArrayList<>(carUsePreference.entrySet());
                    Collections.sort(sortedPreference, Map.Entry.comparingByValue());

                    //Step 2: check availability and choose mode for Work tours by the order of preference
                    for (Map.Entry<Person, Double> entry : sortedPreference) {
                        entry.getKey().getPlan().getTours().values().forEach(tour -> {
                            if (tour.getMainActivity().getPurpose().equals(Purpose.WORK)) {
                                tourModeChoice.checkCarAvailabilityAndChooseMode(household, entry.getKey(), tour, Purpose.WORK);
                            }
                        });
                    }
                } else {
                    //check availability and choose mode for other tours by the order of (education > accompany > other > shopping > recreational)
                    for (Person person : household.getPersons()) {
                        person.getPlan().getTours().values().forEach(tour -> {
                            if (tour.getMainActivity().getPurpose().equals(purpose)) {
                                tourModeChoice.checkCarAvailabilityAndChooseMode(household, person, tour, purpose);
                            }
                        });
                    }
                }
            }
        } else {
            //TODO: for the household has no car, car is still available for mode choice? (e.g. car share, taxi)
            for (Person person : household.getPersons()) {
                person.getPlan().getTours().values().forEach(tour -> {
                    tourModeChoice.chooseMode(person, tour, tour.getMainActivity().getPurpose(), Boolean.FALSE);
                });
            }
        }


        for (Person person : household.getPersons()) {
            List<Tour> mandatoryTours = person.getPlan().getTours().values().stream().filter(tour -> Purpose.getMandatoryPurposes().contains(tour.getMainActivity().getPurpose())).collect(Collectors.toList());
            for (Tour tour : mandatoryTours) {
                boolean hasSubtour = subtourGenerator.hasSubtourInMandatoryActivity(tour);
                if (hasSubtour) {
                    Activity subtourActivity = new Activity(person, Purpose.SUBTOUR);
                    subtourActivity.setTour(tour);
                    subtourTimeAssignment.assignTimeToSubtourActivity(subtourActivity, tour.getMainActivity());
                    subtourDestinationChoice.chooseSubtourDestination(subtourActivity, tour.getMainActivity());
                    planTools.addSubtour(subtourActivity, tour);
                    subtourModeChoice.chooseSubtourMode(tour);
                }
            }
        }
    }

    int counterNonEmployedOrStudentWithMandAct;
    int counterDiscActsOfNonEmployedStudentWithMandAct;

    // Count total number of Activity instances in the map
    private static int countTotalActivities(SortedMap<Purpose, List<Activity>> map) {
        int totalCount = 0;

        for (List<Activity> activityList : map.values()) {
            totalCount += activityList.size();
        }

        return totalCount;
    }

    private void createPlanForOnePerson(Person person) {

        Plan plan = Plan.initializePlan(person);

        bikeOwnershipModel.assignBicycleOwnership(person);
        habitualModeChoice.chooseHabitualMode(person);

        for (Purpose purpose : Purpose.getMandatoryPurposes()) {
            int numberOfDaysWithMandatoryAct = frequencyGenerators.get(purpose).calculateNumberOfActivitiesPerWeek(person, purpose);
            //TODO Ana has new job properties, this model needs be killed after updating the sp reader
            DayOfWeek[] dayOfWeeks = dayOfWeekMandatoryAssignment.assignDaysOfWeek(numberOfDaysWithMandatoryAct, purpose, person);

            for (DayOfWeek day : dayOfWeeks) {
                Activity activity = new Activity(person, purpose);
                activity.setDayOfWeek(day);
                timeAssignment.assignDurationAndThenStartTime(activity);
                if (purpose.equals(Purpose.WORK)){
                    if (person.getJob()!=null){
                        activity.setLocation(person.getJob().getLocation());
                    }else{
                        destinationChoice.selectMainActivityDestination(person, activity);
                    }

                }else{
                    if (person.getSchool()!=null){
                        activity.setLocation(person.getSchool().getLocation());
                    }else{
                        destinationChoice.selectMainActivityDestination(person, activity);
                    }
                }



                int maxTrial = 0;
                while (!plan.getBlockedTimeOfDay().isAvailable(activity.getStartTime_min(), activity.getEndTime_min()) && maxTrial <= TRIALS_RESCHEDULING) {
                    timeAssignment.assignDurationAndThenStartTime(activity);
                    if (purpose.equals(Purpose.WORK)){
                        if (person.getJob()!=null){
                            activity.setLocation(person.getJob().getLocation());
                        }else{
                            destinationChoice.selectMainActivityDestination(person, activity);
                        }

                    }else{
                        if (person.getSchool()!=null){
                            activity.setLocation(person.getSchool().getLocation());
                        }else{
                            destinationChoice.selectMainActivityDestination(person, activity);
                        }
                    }
                    maxTrial += 1;
                }

                planTools.addMainTour(plan, activity);


            }
        }


        SortedMap<Purpose, List<Activity>> discretionaryActivitiesMap = new TreeMap<>();
        List<Activity> stopsOnMandatory = new ArrayList<>();
        List<Activity> accompanyActsOnDiscretionaryTours = new ArrayList<>();
        List<Activity> shoppingActsOnDiscretionaryTours = new ArrayList<>();
        List<Activity> otherActsOnDiscretionaryTours = new ArrayList<>();
        List<Activity> recreationActsOnDiscretionaryTours = new ArrayList<>();


        for (Purpose purpose : Purpose.getDiscretionaryPurposes()) {
            int numAct = frequencyGenerators.get(purpose).calculateNumberOfActivitiesPerWeek(person, purpose);
            for (int i = 0; i < numAct; i++) {
                Activity activity = new Activity(person, purpose);
                discretionaryActivitiesMap.putIfAbsent(purpose, new ArrayList<>());
                discretionaryActivitiesMap.get(purpose).add(activity);

                splitByType.assignActType(activity, person);


                switch (activity.getDiscretionaryActivityType()) {
                    case ON_MANDATORY_TOUR:
                        stopsOnMandatory.add(activity);
                        break;
                    case ON_DISCRETIONARY_TOUR:
                        if (activity.getPurpose() == Purpose.ACCOMPANY) {
                            accompanyActsOnDiscretionaryTours.add(activity);
                        } else if (activity.getPurpose() == Purpose.SHOPPING) {
                            shoppingActsOnDiscretionaryTours.add(activity);
                        } else if (activity.getPurpose() == Purpose.OTHER) {
                            otherActsOnDiscretionaryTours.add(activity);
                        } else {
                            recreationActsOnDiscretionaryTours.add(activity);
                        }
                        break;
                }
            }

        }

        long mandatoryTours = person.getPlan().getTours().values().stream().filter(t -> Purpose.getMandatoryPurposes().contains(t.getMainActivity().getPurpose())).count();


        if (person.getOccupation() != Occupation.STUDENT && person.getOccupation() != Occupation.EMPLOYED && mandatoryTours > 0) {
            counterNonEmployedOrStudentWithMandAct++;
            // Count the total number of Activity instances
            int totalActivityCount = countTotalActivities(discretionaryActivitiesMap);
            counterDiscActsOfNonEmployedStudentWithMandAct = counterDiscActsOfNonEmployedStudentWithMandAct + totalActivityCount;
        }

        stopsOnMandatory.forEach(activity -> {
            Tour selectedTour = planTools.findMandatoryTour(plan);
            activity.setDayOfWeek(selectedTour.getMainActivity().getDayOfWeek());
            //the order of time assignment and stopSplitByType is not yet decided
            timeAssignment.assignDurationToStop(activity); //till this step, we should know whether the current trip is before or after mandatory activity
            StopType stopType = stopSplitType.getStopType(person, activity, selectedTour);

            if (stopType != null) {
                if (stopType.equals(StopType.BEFORE)) {
                    destinationChoice.selectStopDestination(person, selectedTour, activity);
                    planTools.addStopBefore(plan, activity, selectedTour);
                } else {
                    destinationChoice.selectStopDestination(person, selectedTour, activity);
                    planTools.addStopAfter(plan, activity, selectedTour);
                }
            }
        });

        for (Activity activity : accompanyActsOnDiscretionaryTours) {
            int numAccompanyActsNotOnMandatoryTours = accompanyActsOnDiscretionaryTours.size();

            splitByType.assignActTypeForDiscretionaryTourActs(activity, person, numAccompanyActsNotOnMandatoryTours);

            if (activity.getDiscretionaryActivityType() == DiscretionaryActivityType.ACCOMPANY_PRIMARY) {
                dayOfWeekDiscretionaryAssignment.assignDayOfWeek(activity);
                timeAssignment.assignDurationAndThenStartTime(activity);
                destinationChoice.selectMainActivityDestination(person, activity);

                int maxTrial = 0;
                while (!plan.getBlockedTimeOfDay().isAvailable(activity.getStartTime_min(), activity.getEndTime_min()) && maxTrial <= TRIALS_RESCHEDULING) {
                    timeAssignment.assignDurationAndThenStartTime(activity);
                    destinationChoice.selectMainActivityDestination(person, activity);
                    maxTrial += 1;
                }

                planTools.addMainTour(plan, activity);
            } else {
                Tour selectedTour = planTools.findDiscretionaryTourByPurpose(plan, Purpose.ACCOMPANY);
                activity.setDayOfWeek(selectedTour.getMainActivity().getDayOfWeek());
                //the order of time assignment and stopSplitByType is not yet decided
                timeAssignment.assignDurationToStop(activity);
                StopType stopType = stopSplitType.getStopType(person, activity, selectedTour);
                if (stopType != null) {
                    if (stopType.equals(StopType.BEFORE)) {
                        int tempTime = selectedTour.getActivities().firstKey();
                        Activity firstActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopBefore(plan, activity, selectedTour);
                    } else {
                        int tempTime = selectedTour.getActivities().lastKey();
                        Activity lastActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        //timeAssignment.assignDurationToStop(activity); //till this step, we should know whether the current trip is before or after mandatory activity
                        planTools.addStopAfter(plan, activity, selectedTour);
                    }
                } else {
                    //logger.warn("Stops without a valid type: " + stopWithoutTypecounter.incrementAndGet());
                }
            }
        }

        for (Activity activity : shoppingActsOnDiscretionaryTours) {
            int numAccompanyActsNotOnMandatoryTours = shoppingActsOnDiscretionaryTours.size();
            splitByType.assignActTypeForDiscretionaryTourActs(activity, person, numAccompanyActsNotOnMandatoryTours);

            if (activity.getDiscretionaryActivityType() == DiscretionaryActivityType.SHOP_PRIMARY) {
                dayOfWeekDiscretionaryAssignment.assignDayOfWeek(activity);
                timeAssignment.assignDurationAndThenStartTime(activity);
                destinationChoice.selectMainActivityDestination(person, activity);

                int maxTrial = 0;
                while (!plan.getBlockedTimeOfDay().isAvailable(activity.getStartTime_min(), activity.getEndTime_min()) && maxTrial <= TRIALS_RESCHEDULING) {
                    timeAssignment.assignDurationAndThenStartTime(activity);
                    destinationChoice.selectMainActivityDestination(person, activity);
                    maxTrial += 1;
                }

                planTools.addMainTour(plan, activity);
            } else if (activity.getDiscretionaryActivityType() == DiscretionaryActivityType.SHOP_ON_ACCOMPANY) {
                Tour selectedTour = planTools.findDiscretionaryTourByPurpose(plan, Purpose.ACCOMPANY);
                activity.setDayOfWeek(selectedTour.getMainActivity().getDayOfWeek());
                timeAssignment.assignDurationToStop(activity);
                StopType stopType = stopSplitType.getStopType(person, activity, selectedTour);
                if (stopType != null) {
                    if (stopType.equals(StopType.BEFORE)) {
                        int tempTime = selectedTour.getActivities().firstKey();
                        Activity firstActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopBefore(plan, activity, selectedTour);
                    } else {
                        int tempTime = selectedTour.getActivities().lastKey();
                        Activity lastActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopAfter(plan, activity, selectedTour);
                    }
                }
            } else {
                Tour selectedTour = planTools.findDiscretionaryTourByPurpose(plan, Purpose.SHOPPING);
                activity.setDayOfWeek(selectedTour.getMainActivity().getDayOfWeek());
                timeAssignment.assignDurationToStop(activity);
                StopType stopType = stopSplitType.getStopType(person, activity, selectedTour);
                if (stopType != null) {
                    if (stopType.equals(StopType.BEFORE)) {
                        int tempTime = selectedTour.getActivities().firstKey();
                        Activity firstActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopBefore(plan, activity, selectedTour);
                    } else {
                        int tempTime = selectedTour.getActivities().lastKey();
                        Activity lastActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopAfter(plan, activity, selectedTour);
                    }
                }
            }
        }

        for (Activity activity : otherActsOnDiscretionaryTours) {
            int numAccompanyActsNotOnMandatoryTours = otherActsOnDiscretionaryTours.size();
            splitByType.assignActTypeForDiscretionaryTourActs(activity, person, numAccompanyActsNotOnMandatoryTours);

            if (activity.getDiscretionaryActivityType() == DiscretionaryActivityType.OTHER_PRIMARY) {
                dayOfWeekDiscretionaryAssignment.assignDayOfWeek(activity);
                timeAssignment.assignDurationAndThenStartTime(activity);
                destinationChoice.selectMainActivityDestination(person, activity);

                int maxTrial = 0;
                while (!plan.getBlockedTimeOfDay().isAvailable(activity.getStartTime_min(), activity.getEndTime_min()) && maxTrial <= TRIALS_RESCHEDULING) {
                    timeAssignment.assignDurationAndThenStartTime(activity);
                    destinationChoice.selectMainActivityDestination(person, activity);
                    maxTrial += 1;
                }

                planTools.addMainTour(plan, activity);
            } else if (activity.getDiscretionaryActivityType() == DiscretionaryActivityType.OTHER_ON_ACCOMPANY) {
                Tour selectedTour = planTools.findDiscretionaryTourByPurpose(plan, Purpose.ACCOMPANY);
                activity.setDayOfWeek(selectedTour.getMainActivity().getDayOfWeek());
                timeAssignment.assignDurationToStop(activity);
                StopType stopType = stopSplitType.getStopType(person, activity, selectedTour);
                if (stopType != null) {
                    if (stopType.equals(StopType.BEFORE)) {
                        int tempTime = selectedTour.getActivities().firstKey();
                        Activity firstActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopBefore(plan, activity, selectedTour);
                    } else {
                        int tempTime = selectedTour.getActivities().lastKey();
                        Activity lastActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopAfter(plan, activity, selectedTour);
                    }
                }
            } else if (activity.getDiscretionaryActivityType() == DiscretionaryActivityType.OTHER_ON_SHOP) {
                Tour selectedTour = planTools.findDiscretionaryTourByPurpose(plan, Purpose.SHOPPING);
                activity.setDayOfWeek(selectedTour.getMainActivity().getDayOfWeek());
                timeAssignment.assignDurationToStop(activity);
                StopType stopType = stopSplitType.getStopType(person, activity, selectedTour);
                if (stopType != null) {
                    if (stopType.equals(StopType.BEFORE)) {
                        int tempTime = selectedTour.getActivities().firstKey();
                        Activity firstActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopBefore(plan, activity, selectedTour);
                    } else {
                        int tempTime = selectedTour.getActivities().lastKey();
                        Activity lastActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopAfter(plan, activity, selectedTour);
                    }
                }
            } else if (activity.getDiscretionaryActivityType() == DiscretionaryActivityType.OTHER_ON_OTHER) {
                Tour selectedTour = planTools.findDiscretionaryTourByPurpose(plan, Purpose.OTHER);
                activity.setDayOfWeek(selectedTour.getMainActivity().getDayOfWeek());
                timeAssignment.assignDurationToStop(activity);
                StopType stopType = stopSplitType.getStopType(person, activity, selectedTour);
                if (stopType != null) {
                    if (stopType.equals(StopType.BEFORE)) {
                        int tempTime = selectedTour.getActivities().firstKey();
                        Activity firstActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopBefore(plan, activity, selectedTour);
                    } else {
                        int tempTime = selectedTour.getActivities().lastKey();
                        Activity lastActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopAfter(plan, activity, selectedTour);
                    }
                }
            }
        }

        for (Activity activity : recreationActsOnDiscretionaryTours) {
            int numAccompanyActsNotOnMandatoryTours = otherActsOnDiscretionaryTours.size();
            splitByType.assignActTypeForDiscretionaryTourActs(activity, person, numAccompanyActsNotOnMandatoryTours);

            if (activity.getDiscretionaryActivityType() == DiscretionaryActivityType.RECREATION_PRIMARY) {
                dayOfWeekDiscretionaryAssignment.assignDayOfWeek(activity);
                timeAssignment.assignDurationAndThenStartTime(activity);
                destinationChoice.selectMainActivityDestination(person, activity);

                int maxTrial = 0;
                while (!plan.getBlockedTimeOfDay().isAvailable(activity.getStartTime_min(), activity.getEndTime_min()) && maxTrial <= TRIALS_RESCHEDULING) {
                    timeAssignment.assignDurationAndThenStartTime(activity);
                    destinationChoice.selectMainActivityDestination(person, activity);
                    maxTrial += 1;
                }

                planTools.addMainTour(plan, activity);
            } else if (activity.getDiscretionaryActivityType() == DiscretionaryActivityType.RECREATION_ON_ACCOMPANY) {
                Tour selectedTour = planTools.findDiscretionaryTourByPurpose(plan, Purpose.ACCOMPANY);
                if (selectedTour == null) {

                }
                activity.setDayOfWeek(selectedTour.getMainActivity().getDayOfWeek());
                timeAssignment.assignDurationToStop(activity);
                StopType stopType = stopSplitType.getStopType(person, activity, selectedTour);
                if (stopType != null) {
                    if (stopType.equals(StopType.BEFORE)) {
                        int tempTime = selectedTour.getActivities().firstKey();
                        Activity firstActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopBefore(plan, activity, selectedTour);
                    } else {
                        int tempTime = selectedTour.getActivities().lastKey();
                        Activity lastActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopAfter(plan, activity, selectedTour);
                    }
                }
            } else if (activity.getDiscretionaryActivityType() == DiscretionaryActivityType.RECREATION_ON_SHOP) {
                Tour selectedTour = planTools.findDiscretionaryTourByPurpose(plan, Purpose.SHOPPING);
                activity.setDayOfWeek(selectedTour.getMainActivity().getDayOfWeek());
                timeAssignment.assignDurationToStop(activity);
                StopType stopType = stopSplitType.getStopType(person, activity, selectedTour);
                if (stopType != null) {
                    if (stopType.equals(StopType.BEFORE)) {
                        int tempTime = selectedTour.getActivities().firstKey();
                        Activity firstActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopBefore(plan, activity, selectedTour);
                    } else {
                        int tempTime = selectedTour.getActivities().lastKey();
                        Activity lastActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopAfter(plan, activity, selectedTour);
                    }
                }
            } else if (activity.getDiscretionaryActivityType() == DiscretionaryActivityType.RECREATION_ON_OTHER) {
                Tour selectedTour = planTools.findDiscretionaryTourByPurpose(plan, Purpose.OTHER);
                activity.setDayOfWeek(selectedTour.getMainActivity().getDayOfWeek());
                timeAssignment.assignDurationToStop(activity);
                StopType stopType = stopSplitType.getStopType(person, activity, selectedTour);
                if (stopType != null) {
                    if (stopType.equals(StopType.BEFORE)) {
                        int tempTime = selectedTour.getActivities().firstKey();
                        Activity firstActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopBefore(plan, activity, selectedTour);
                    } else {
                        int tempTime = selectedTour.getActivities().lastKey();
                        Activity lastActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopAfter(plan, activity, selectedTour);
                    }
                }
            } else if (activity.getDiscretionaryActivityType() == DiscretionaryActivityType.RECREATION_ON_RECREATION) {
                Tour selectedTour = planTools.findDiscretionaryTourByPurpose(plan, Purpose.RECREATION);
                activity.setDayOfWeek(selectedTour.getMainActivity().getDayOfWeek());
                timeAssignment.assignDurationToStop(activity);
                StopType stopType = stopSplitType.getStopType(person, activity, selectedTour);
                if (stopType != null) {
                    if (stopType.equals(StopType.BEFORE)) {
                        int tempTime = selectedTour.getActivities().firstKey();
                        Activity firstActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopBefore(plan, activity, selectedTour);
                    } else {
                        int tempTime = selectedTour.getActivities().lastKey();
                        Activity lastActivity = selectedTour.getActivities().get(tempTime);
                        destinationChoice.selectStopDestination(person, selectedTour, activity);
                        planTools.addStopAfter(plan, activity, selectedTour);
                    }
                }
            }
        }
    }

    @Override
    public Object call() throws Exception {
        AtomicInteger counter = new AtomicInteger(0);
        for (Household household : this.households) {
            createPlanForOneHousehold(household);
            counter.incrementAndGet();
            final int i = counter.get();
            if ((i % 1000) == 0) {
                logger.info("Completed " + i + " households by thread " + thread);
            }

        }
        return null;
    }
}
