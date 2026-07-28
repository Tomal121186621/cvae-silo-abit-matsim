package abm.utils;

import abm.data.plans.*;
import abm.data.timeOfDay.BlockedTimeOfWeekLinkedList;
import abm.data.travelInformation.TravelTimes;
import abm.properties.InternalProperties;

import java.time.DayOfWeek;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;


public class PlanTools {

    private final TravelTimes travelTimes;

    public PlanTools(TravelTimes travelTimes) {
        this.travelTimes = travelTimes;
    }

    public static int endOfTheWeek() {
        return 7 * 24 * 60;
    }

    public static int startOfTheWeek() {
        return 0;
    }


    /**
     * Adds a main activity tour. Cuts the home activity into two pieces, one before the tour and another after the tour
     * Adds trips
     *
     * @param mainTourActivity
     */
    public void addMainTour(Plan plan, Activity mainTourActivity) {

        //Todo is there already a tour in the chosen day?
        DayOfWeek dayOfWeek = mainTourActivity.getDayOfWeek();
        int startTimeOfTheDay_min = dayOfWeek.ordinal() * 24 * 60;
        int endTimeOfTheDay_min = (dayOfWeek.ordinal() + 1) * 24 * 60 - 1;
        int numberOfExistingTourOfTheDay = (int) plan.getTours().keySet().stream()
                .filter(tourStartTime -> tourStartTime >= startTimeOfTheDay_min && tourStartTime <= endTimeOfTheDay_min)
                .count();

        if (numberOfExistingTourOfTheDay == 0) {
            addTheFirstTourOfTheDay(plan, mainTourActivity, startTimeOfTheDay_min, endTimeOfTheDay_min);
        } else if (numberOfExistingTourOfTheDay > 0) {
            addOtherToursOfTheDay(plan, mainTourActivity, startTimeOfTheDay_min, endTimeOfTheDay_min);
        } else {
            System.out.println("Error in calculating number of tours of a day");
        }

    }

    private void addOtherToursOfTheDay(Plan plan, Activity mainTourActivity, int startTimeOfTheDay_min, int endTimeOfTheDay_min) {

        int travelTimeToMainActivity_min = travelTimes.getTravelTimeInMinutes(plan.getDummyHomeActivity().getLocation(), mainTourActivity.getLocation(), Mode.UNKNOWN, mainTourActivity.getStartTime_min());
        int timeLeavingHome_min = mainTourActivity.getStartTime_min() - travelTimeToMainActivity_min;
        int travelTimeBackFromMainActivity_min = travelTimes.getTravelTimeInMinutes(mainTourActivity.getLocation(), plan.getDummyHomeActivity().getLocation(), Mode.UNKNOWN, mainTourActivity.getStartTime_min());
        int timeArrivingHome_min = mainTourActivity.getEndTime_min() + travelTimeBackFromMainActivity_min;


        if (plan.getBlockedTimeOfDay().isAvailable(timeLeavingHome_min, timeArrivingHome_min)) {

            //Todo select tours of the day
            List<Integer> timeIndexOfPotentialAffectedTours = plan.getTours().keySet().stream()
                    .filter(tourStartTime -> tourStartTime >= startTimeOfTheDay_min && tourStartTime <= endTimeOfTheDay_min)
                    .collect(Collectors.toList());


            //Todo Identify which tour and which part of the tour will be affected (before the exisiting tour or after)
            for (Integer timeIndex : timeIndexOfPotentialAffectedTours) {

                Tour tempTour = plan.getTours().get(timeIndex);
                int indexOfFirstLeg = tempTour.getLegs().firstKey();
                int indexOfLastLeg = tempTour.getLegs().lastKey();
                Activity firstHomeAct = tempTour.getLegs().get(indexOfFirstLeg).getPreviousActivity();
                Activity secondHomeAct = tempTour.getLegs().get(indexOfLastLeg).getNextActivity();

                if (firstHomeAct.getStartTime_min() <= mainTourActivity.getStartTime_min() && firstHomeAct.getEndTime_min() >= mainTourActivity.getEndTime_min()) {

                    //Todo add activities and legs to the new tour
                    Activity homeActBeforeMainAct = new Activity(mainTourActivity.getPerson(), Purpose.HOME);
                    homeActBeforeMainAct.setStartTime_min(startTimeOfTheDay_min);
                    homeActBeforeMainAct.setEndTime_min(timeLeavingHome_min);
                    homeActBeforeMainAct.setLocation(plan.getDummyHomeActivity().getLocation());
                    homeActBeforeMainAct.setDayOfWeek(mainTourActivity.getDayOfWeek());

                    final Leg firstLeg = new Leg(homeActBeforeMainAct, mainTourActivity);
                    firstLeg.setTravelTime_min(travelTimeToMainActivity_min);

                    Activity homeActAfterMainAct = new Activity(mainTourActivity.getPerson(), Purpose.HOME);
                    homeActAfterMainAct.setStartTime_min(timeArrivingHome_min);
                    homeActAfterMainAct.setEndTime_min(firstHomeAct.getEndTime_min());
                    homeActAfterMainAct.setLocation(plan.getDummyHomeActivity().getLocation());
                    homeActAfterMainAct.setDayOfWeek(mainTourActivity.getDayOfWeek());

                    final Leg secondLeg = new Leg(mainTourActivity, homeActAfterMainAct);
                    secondLeg.setTravelTime_min(travelTimeToMainActivity_min);

                    //Todo modify home act on the selected tour
                    firstHomeAct.setStartTime_min(timeArrivingHome_min);

                    Tour tour = new Tour(mainTourActivity, plan.getTours().size() + 1);
                    tour.getLegs().put(timeLeavingHome_min, firstLeg);
                    tour.getLegs().put(mainTourActivity.getEndTime_min(), secondLeg);
                    mainTourActivity.setTour(tour);
                    plan.getBlockedTimeOfDay().blockTime(mainTourActivity.getStartTime_min(), mainTourActivity.getEndTime_min());
                    plan.getTours().put(mainTourActivity.getStartTime_min(), tour);
                    break;

                }

                if (secondHomeAct.getStartTime_min() <= mainTourActivity.getStartTime_min() && secondHomeAct.getEndTime_min() >= mainTourActivity.getEndTime_min()) {

                    //Todo add activities and legs to the new tour
                    Activity homeActBeforeMainAct = new Activity(mainTourActivity.getPerson(), Purpose.HOME);
                    homeActBeforeMainAct.setStartTime_min(secondHomeAct.getStartTime_min());
                    homeActBeforeMainAct.setEndTime_min(timeLeavingHome_min);
                    homeActBeforeMainAct.setLocation(plan.getDummyHomeActivity().getLocation());
                    homeActBeforeMainAct.setDayOfWeek(mainTourActivity.getDayOfWeek());

                    final Leg firstLeg = new Leg(homeActBeforeMainAct, mainTourActivity);
                    firstLeg.setTravelTime_min(travelTimeToMainActivity_min);

                    Activity homeActAfterMainAct = new Activity(mainTourActivity.getPerson(), Purpose.HOME);
                    homeActAfterMainAct.setStartTime_min(timeArrivingHome_min);
                    homeActAfterMainAct.setEndTime_min(endTimeOfTheDay_min);
                    homeActAfterMainAct.setLocation(plan.getDummyHomeActivity().getLocation());
                    homeActAfterMainAct.setDayOfWeek(mainTourActivity.getDayOfWeek());

                    final Leg secondLeg = new Leg(mainTourActivity, homeActAfterMainAct);
                    secondLeg.setTravelTime_min(travelTimeToMainActivity_min);

                    //Todo modify home act on the selected tour
                    secondHomeAct.setEndTime_min(timeLeavingHome_min);

                    Tour tour = new Tour(mainTourActivity, plan.getTours().size() + 1);
                    tour.getLegs().put(timeLeavingHome_min, firstLeg);
                    tour.getLegs().put(mainTourActivity.getEndTime_min(), secondLeg);
                    mainTourActivity.setTour(tour);
                    plan.getBlockedTimeOfDay().blockTime(mainTourActivity.getStartTime_min(), mainTourActivity.getEndTime_min());
                    plan.getTours().put(mainTourActivity.getStartTime_min(), tour);
                    break;

                }
            }

        } else {
            plan.addUnmetActivities(mainTourActivity.getStartTime_min(), mainTourActivity);
        }
    }

    private void addTheFirstTourOfTheDay(Plan plan, Activity mainTourActivity, int startTimeOfTheDay_min, int endTimeOfTheDay_min) {

        int travelTimeToMainActivity_min = travelTimes.getTravelTimeInMinutes(plan.getDummyHomeActivity().getLocation(), mainTourActivity.getLocation(), Mode.UNKNOWN, mainTourActivity.getStartTime_min());
        int timeLeavingHome_min = mainTourActivity.getStartTime_min() - travelTimeToMainActivity_min;

        Activity homeActBeforeMainAct = new Activity(mainTourActivity.getPerson(), Purpose.HOME);
        homeActBeforeMainAct.setStartTime_min(startTimeOfTheDay_min);
        homeActBeforeMainAct.setEndTime_min(timeLeavingHome_min);
        homeActBeforeMainAct.setLocation(plan.getDummyHomeActivity().getLocation());
        homeActBeforeMainAct.setDayOfWeek(mainTourActivity.getDayOfWeek());

        final Leg firstLeg = new Leg(homeActBeforeMainAct, mainTourActivity);
        firstLeg.setTravelTime_min(travelTimeToMainActivity_min);

        int travelTimeBackFromMainActivity_min = travelTimes.getTravelTimeInMinutes(mainTourActivity.getLocation(), plan.getDummyHomeActivity().getLocation(), Mode.UNKNOWN, mainTourActivity.getStartTime_min());
        int timeArrivingHome_min = mainTourActivity.getEndTime_min() + travelTimeBackFromMainActivity_min;

        Activity homeActAfterMainAct = new Activity(mainTourActivity.getPerson(), Purpose.HOME);
        homeActAfterMainAct.setStartTime_min(timeArrivingHome_min);
        homeActAfterMainAct.setEndTime_min(endTimeOfTheDay_min);
        homeActAfterMainAct.setLocation(plan.getDummyHomeActivity().getLocation());
        homeActAfterMainAct.setDayOfWeek(mainTourActivity.getDayOfWeek());

        final Leg secondLeg = new Leg(mainTourActivity, homeActAfterMainAct);
        secondLeg.setTravelTime_min(travelTimeToMainActivity_min);

        if (plan.getBlockedTimeOfDay().isAvailable(timeLeavingHome_min, timeArrivingHome_min)) {
            Tour tour = new Tour(mainTourActivity, plan.getTours().size() + 1);
            tour.getLegs().put(timeLeavingHome_min, firstLeg);
            tour.getLegs().put(mainTourActivity.getEndTime_min(), secondLeg);
            mainTourActivity.setTour(tour);
            plan.getBlockedTimeOfDay().blockTime(mainTourActivity.getStartTime_min(), mainTourActivity.getEndTime_min());
            plan.getTours().put(mainTourActivity.getStartTime_min(), tour);
        } else {
            plan.addUnmetActivities(mainTourActivity.getStartTime_min(), mainTourActivity);
        }
    }


    /**
     * Adds a main activity subtour. Cuts the main activity into two pieces, one before the tour and another after the tour
     * Adds trips
     *
     * @param subTourActivity
     */
    public void addSubtour(Activity subTourActivity, Tour tour) {
        Activity mainActivity = tour.getMainActivity();

        int timeToSubTourActivity = travelTimes.getTravelTimeInMinutes(mainActivity.getLocation(), subTourActivity.getLocation(), Mode.UNKNOWN, subTourActivity.getStartTime_min());

        final Subtour subtour = new Subtour(mainActivity, subTourActivity, timeToSubTourActivity);
        mainActivity.setSubtour(subtour);
        subtour.getOutboundLeg().setTravelTime_min(timeToSubTourActivity);
        subtour.getInboundLeg().setTravelTime_min(timeToSubTourActivity);




       /* //add the new activity and break the main activity of the tour
        if (mainActivity != null) {
            int timeToSubTourActivity = travelTimes.getTravelTimeInMinutes(mainActivity.getLocation(), subTourActivity.getLocation(), Mode.UNKNOWN, subTourActivity.getStartTime_min());
            int previousEndOfMainActivity = mainActivity.getEndTime_min();
            Leg previousLegFromMainActivity = tour.getLegs().get(mainActivity);

            //cut the main activity to its first part
            mainActivity.setEndTime_min(subTourActivity.getStartTime_min() - timeToSubTourActivity);

            //adds a leg to the subtour
            tour.getLegs().put(mainActivity.getEndTime_min(), new Leg(mainActivity, subTourActivity));

            //adds the subtour activity
            tour.getActivities().put(subTourActivity.getStartTime_min(), subTourActivity);

            //adds the second part of the main activity
            Activity secondMainActivity = new Activity(mainActivity.getPerson(), mainActivity.getPurpose());
            secondMainActivity.setStartTime_min(subTourActivity.getEndTime_min() + timeToSubTourActivity);
            secondMainActivity.setEndTime_min(previousEndOfMainActivity);
            secondMainActivity.setLocation(mainActivity.getLocation());
            tour.getActivities().put(secondMainActivity.getStartTime_min(), secondMainActivity);


            //adds the return leg from the subtour
            final Leg secondSubtourLeg = new Leg(subTourActivity, secondMainActivity);
            tour.getLegs().put(subTourActivity.getEndTime_min(), secondSubtourLeg);

            //adds the final leg (and remove the older one, since it is indexed by the previous main activity)
            tour.getLegs().remove(mainActivity);
            tour.getLegs().put(secondMainActivity.getEndTime_min(), new Leg(secondMainActivity, previousLegFromMainActivity.getNextActivity()));
        } else {
            //trying to add a subtour without having a tour!
        }
*/
    }

    /**
     * Adds one stop before the next main activity, modifying the home activity accordingly
     * Changes the outbound trip and splits it into two subtrips
     */
    public void addStopBefore(Plan plan, Activity stopBefore, Tour tour) {

        Activity firstNonHomeActInExistingTour = tour.getActivities().get(tour.getActivities().firstKey());
        final int timeLeavingFromHomeBeforeAddingStop_min = tour.getLegs().firstKey();

        int travelTimeForFirstLeg = travelTimes.getTravelTimeInMinutes(tour.getLegs().get(timeLeavingFromHomeBeforeAddingStop_min).getPreviousActivity().getLocation(),
                stopBefore.getLocation(), Mode.UNKNOWN, timeLeavingFromHomeBeforeAddingStop_min);
        int travelTimeForSecondLeg = travelTimes.getTravelTimeInMinutes(stopBefore.getLocation(), firstNonHomeActInExistingTour.getLocation(),
                Mode.UNKNOWN, firstNonHomeActInExistingTour.getStartTime_min());

        final int duration = stopBefore.getDuration();
        int stopBefore_StartTime_min = (int) (Math.floor((double) firstNonHomeActInExistingTour.getStartTime_min() / InternalProperties.SEARCH_INTERVAL_MIN) * InternalProperties.SEARCH_INTERVAL_MIN - duration - travelTimeForSecondLeg);
        stopBefore.setStartTime_min(stopBefore_StartTime_min);
        stopBefore.setEndTime_min(stopBefore_StartTime_min + duration);

        Leg firstLeg = new Leg(tour.getLegs().get(timeLeavingFromHomeBeforeAddingStop_min).getPreviousActivity(), stopBefore);
        tour.getLegs().get(timeLeavingFromHomeBeforeAddingStop_min).getPreviousActivity().setEndTime_min(stopBefore_StartTime_min - travelTimeForFirstLeg);
        firstLeg.setTravelTime_min(travelTimeForFirstLeg);
        Leg secondLeg = new Leg(stopBefore, firstNonHomeActInExistingTour);
        secondLeg.setTravelTime_min(travelTimeForSecondLeg);

        BlockedTimeOfWeekLinkedList tempBlockedTimeOfWeek = plan.getBlockedTimeOfDay();
        //tempBlockedTimeOfWeek.setAvailable(timeLeavingFromHomeBeforeAddingStop_min, firstNonHomeActInExistingTour.getStartTime_min());

        if (tempBlockedTimeOfWeek.isAvailable(firstLeg.getPreviousActivity().getEndTime_min(), secondLeg.getPreviousActivity().getEndTime_min() + secondLeg.getTravelTime_min() - InternalProperties.SEARCH_INTERVAL_MIN)) {
            tour.getLegs().remove(timeLeavingFromHomeBeforeAddingStop_min);
            tour.getActivities().put(stopBefore_StartTime_min, stopBefore);
            tour.getLegs().put(stopBefore_StartTime_min - travelTimeForFirstLeg, firstLeg);
            tour.getLegs().put(secondLeg.getPreviousActivity().getEndTime_min(), secondLeg);
            plan.getBlockedTimeOfDay().blockTime(stopBefore.getStartTime_min(), stopBefore.getEndTime_min());
            stopBefore.setTour(tour);
        } else {
            plan.addUnmetActivities(stopBefore_StartTime_min, stopBefore);
        }
    }


    /**
     * Adds one stop after the last activity, modifying the home activity accordingly
     * Changes the inbound trip and splits it into two subtrips
     *
     * @param stopAfter
     * @param stopAfter
     * @param tour
     */
    public void addStopAfter(Plan plan, Activity stopAfter, Tour tour) {

        Activity lastNonHomeActInExistingTour = tour.getActivities().get(tour.getActivities().lastKey());
        final int timeLeavingToHomeBeforeAddingStop_min = tour.getLegs().lastKey();

        int travelTimeForFirstLeg = travelTimes.getTravelTimeInMinutes(lastNonHomeActInExistingTour.getLocation(),
                stopAfter.getLocation(), Mode.UNKNOWN, lastNonHomeActInExistingTour.getEndTime_min());
        int travelTimeForSecondLeg = travelTimes.getTravelTimeInMinutes(stopAfter.getLocation(),
                tour.getLegs().get(timeLeavingToHomeBeforeAddingStop_min).getNextActivity().getLocation(),
                Mode.UNKNOWN, stopAfter.getEndTime_min());

        final int duration = stopAfter.getDuration();
        int stopAfter_StartTime_min = (int) (Math.ceil((double) lastNonHomeActInExistingTour.getEndTime_min() / InternalProperties.SEARCH_INTERVAL_MIN) * InternalProperties.SEARCH_INTERVAL_MIN + travelTimeForFirstLeg);
        stopAfter.setStartTime_min(stopAfter_StartTime_min);
        stopAfter.setEndTime_min(stopAfter_StartTime_min + duration);

        Leg firstLeg = new Leg(lastNonHomeActInExistingTour, stopAfter);
        firstLeg.setTravelTime_min(travelTimeForFirstLeg);
        Leg secondLeg = new Leg(stopAfter, tour.getLegs().get(timeLeavingToHomeBeforeAddingStop_min).getNextActivity());
        tour.getLegs().get(timeLeavingToHomeBeforeAddingStop_min).getNextActivity().setStartTime_min(stopAfter.getEndTime_min() + travelTimeForSecondLeg);
        secondLeg.setTravelTime_min(travelTimeForSecondLeg);

        BlockedTimeOfWeekLinkedList tempBlockedTimeOfWeek = plan.getBlockedTimeOfDay();
        //tempBlockedTimeOfWeek.setAvailable(lastNonHomeActInExistingTour.getEndTime_min(), timeLeavingToHomeBeforeAddingStop_min);

        if (tempBlockedTimeOfWeek.isAvailable(firstLeg.getNextActivity().getStartTime_min() - firstLeg.getTravelTime_min() + InternalProperties.SEARCH_INTERVAL_MIN, secondLeg.getNextActivity().getStartTime_min())) {
            tour.getLegs().remove(timeLeavingToHomeBeforeAddingStop_min);
            tour.getActivities().put(stopAfter_StartTime_min, stopAfter);
            tour.getLegs().put(firstLeg.getPreviousActivity().getEndTime_min(), firstLeg);
            tour.getLegs().put(secondLeg.getPreviousActivity().getEndTime_min(), secondLeg);
            plan.getBlockedTimeOfDay().blockTime(stopAfter.getStartTime_min(), stopAfter.getEndTime_min());
            stopAfter.setTour(tour);
        } else {
            plan.addUnmetActivities(stopAfter_StartTime_min, stopAfter);
        }
    }

    public static Tour findMandatoryTour(Plan plan) {
        final List<Tour> tourList = plan.getTours().values().stream().filter(tour -> Purpose.getMandatoryPurposes().contains(tour.getMainActivity().getPurpose())).collect(Collectors.toList());
        Collections.shuffle(tourList, AbitUtils.getRandomObject());
        return tourList.stream().findFirst().orElse(null);
    }

    public static Tour findDiscretionaryTour(Plan plan) {
        final List<Tour> tourList = plan.getTours().values().stream().filter(tour -> Purpose.getDiscretionaryPurposes().contains(tour.getMainActivity().getPurpose())).collect(Collectors.toList());
        Collections.shuffle(tourList, AbitUtils.getRandomObject());
        return tourList.stream().findFirst().orElse(null);
    }

    public static Tour findDiscretionaryTourByPurpose(Plan plan, Purpose purpose) {
        final List<Tour> tourList = plan.getTours().values().stream().filter(tour -> tour.getMainActivity().getPurpose() == purpose).collect(Collectors.toList());
        Collections.shuffle(tourList, AbitUtils.getRandomObject());
        return tourList.stream().findFirst().orElse(null);
    }
}
