package abm.models.activityGeneration.time;

import abm.data.DataSet;
import abm.data.plans.Activity;
import abm.data.plans.Purpose;
import abm.data.timeOfDay.*;
import abm.properties.AbitResources;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.util.MitoUtil;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.time.DayOfWeek;
import java.util.*;

public class TimeAssignmentModel implements TimeAssignment {

    private final Map<Purpose, TimeOfWeekDistribution> timeOfWeekDistributionMap;
    private final Map<Purpose, Map<StartTimeInterval, DurationDistribution>> durationDistributionMap;
    private final Map<Purpose, Integer> typicalDuration;
    private final DataSet dataSet;

    public TimeAssignmentModel(DataSet dataSet) {
        this.dataSet = dataSet;
        timeOfWeekDistributionMap = new HashMap<>();
        durationDistributionMap = new HashMap<>();

        readTimeOfDayDistributions();
        readDurationDistributions();
        typicalDuration = new HashMap<>();

        calculateTypicalDurations();
    }

    private void calculateTypicalDurations() {
        //do not calculate but provide an average?
        typicalDuration.put(Purpose.WORK, 12 * 60);
        typicalDuration.put(Purpose.EDUCATION, 12 * 60);
        typicalDuration.put(Purpose.SHOPPING, 25);
        typicalDuration.put(Purpose.RECREATION, 2 * 60);
        typicalDuration.put(Purpose.ACCOMPANY, 15);
        typicalDuration.put(Purpose.OTHER, 60);

    }

    StartTimeInterval getInterval(int time_h, Purpose purpose) {
        for (StartTimeInterval timeInterval : durationDistributionMap.get(purpose).keySet()) {
            if (time_h < timeInterval.to) {
                return timeInterval;
            }
        }
        throw new RuntimeException("The start time is not in the day");
    }

    private class StartTimeInterval implements Comparable<StartTimeInterval> {

        int from;
        int to;

        StartTimeInterval(int from, int to) {
            this.from = from;
            this.to = to;
        }

        @Override
        public int compareTo(StartTimeInterval o) {
            return Integer.compare(this.from, o.from);
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (o == null || getClass() != o.getClass()) return false;
            StartTimeInterval that = (StartTimeInterval) o;
            return from == that.from && to == that.to;
        }

        @Override
        public int hashCode() {
            return Objects.hash(from, to);
        }
    }

    private void readDurationDistributions() {
        int timeIndex;
        int purposeIndex;
        int fromIndex;
        int toIndex;
        int probabilityIndex;

        try {
            BufferedReader br = new BufferedReader(new FileReader(AbitResources.instance.getString("duration.distributions")));
            String[] firstLine = br.readLine().split(",");

            timeIndex = MitoUtil.findPositionInArray("duration_min", firstLine);
            purposeIndex = MitoUtil.findPositionInArray("purpose", firstLine);
            fromIndex = MitoUtil.findPositionInArray("start_from_h", firstLine);
            toIndex = MitoUtil.findPositionInArray("start_to_h", firstLine);
            probabilityIndex = MitoUtil.findPositionInArray("duration_prob", firstLine);

            String line;
            while ((line = br.readLine()) != null) {
                int time = Integer.parseInt(line.split(",")[timeIndex]);
                Purpose purpose = Purpose.valueOf(line.split(",")[purposeIndex].toUpperCase());
                int from_h = Integer.parseInt(line.split(",")[fromIndex]);
                int to_h = Integer.parseInt(line.split(",")[toIndex]);

                StartTimeInterval interval = new StartTimeInterval(from_h, to_h);
                //startTimeIntervals.add(interval);

                double probability = Double.parseDouble(line.split(",")[probabilityIndex]);


                durationDistributionMap.putIfAbsent(purpose, new HashMap<>());
                durationDistributionMap.get(purpose).putIfAbsent(interval, new DurationDistribution());
                durationDistributionMap.get(purpose).get(interval).setProbability(time, probability);
            }

        } catch (IOException e) {
            e.printStackTrace();
        }

    }

    private void readTimeOfDayDistributions() {

        int timeIndex;
        int purposeIndex;
        int probabilityIndex;

        try {
            BufferedReader br = new BufferedReader(new FileReader(AbitResources.instance.getString("start.time.distributions")));
            String[] firstLine = br.readLine().split(",");

            timeIndex = MitoUtil.findPositionInArray("time_week_min", firstLine);
            purposeIndex = MitoUtil.findPositionInArray("purpose", firstLine);
            probabilityIndex = MitoUtil.findPositionInArray("start_time_prob", firstLine);

            String line;
            while ((line = br.readLine()) != null) {
                int time = Integer.parseInt(line.split(",")[timeIndex]);
                Purpose purpose = Purpose.valueOf(line.split(",")[purposeIndex].toUpperCase());
                double probability = Double.parseDouble(line.split(",")[probabilityIndex]);

                timeOfWeekDistributionMap.putIfAbsent(purpose, new TimeOfWeekDistribution());
                timeOfWeekDistributionMap.get(purpose).setProbability(time, probability);
            }

        } catch (IOException e) {
            e.printStackTrace();
        }


    }

    @Override
    public void assignStartTimeAndDuration(Activity activity) {

        final DayOfWeek dayOfWeek = activity.getDayOfWeek();
        int travelTime = 30; //default travel time
        int startTime;
        int initialDuration = typicalDuration.get(activity.getPurpose());

        BlockedTimeOfWeekLinkedList blockedTimeOfWeek = activity.getPerson().getPlan().getBlockedTimeOfDay();
        //blockedTimeOfWeek = TimeOfDayUtils.updateAvailableTimeForNextTrip(blockedTimeOfWeek, initialDuration + travelTime); //Todo: why this line? Terminate for a while

        TimeOfWeekDistribution timeOfWeekDistribution = timeOfWeekDistributionMap.get(activity.getPurpose());
        timeOfWeekDistribution = TimeOfDayUtils.updateTODWithAvailability(timeOfWeekDistribution, blockedTimeOfWeek);
        timeOfWeekDistribution = timeOfWeekDistribution.getForThisDayOfWeek(dayOfWeek);

        int midnight = (activity.getDayOfWeek().ordinal()) * 24 * 60;
        int newDuration;

        if (activity.getPurpose() == Purpose.WORK && activity.getPerson().getOccupation() == Occupation.EMPLOYED
                && activity.getPerson().getSiloJobDuration() > 0) {
            newDuration = activity.getPerson().getSiloJobDuration();
            if (dayOfWeek.equals(DayOfWeek.SATURDAY) || dayOfWeek.equals(DayOfWeek.SUNDAY)) {
                startTime = activity.getPerson().getSiloJobStartTimeWeekends() + midnight;
            } else {
                startTime = activity.getPerson().getSiloJobStartTimeWorkdays() + midnight;
            }

            double startTimeProbability = timeOfWeekDistribution.probability(startTime);

            if (startTimeProbability == 0) {
                startTime = timeOfWeekDistribution.selectTime();
                newDuration = durationDistributionMap.get(activity.getPurpose()).get(getInterval((startTime - midnight) / 60, activity.getPurpose())).selectTime();
            }
        } else {
            startTime = timeOfWeekDistribution.selectTime();
            newDuration = durationDistributionMap.get(activity.getPurpose()).get(getInterval((startTime - midnight) / 60, activity.getPurpose())).selectTime();
        }

        if (newDuration + travelTime > initialDuration) {
            //tour does not fit here! Make it shorter
            newDuration = initialDuration;
        }

        activity.setStartTime_min(startTime);
        activity.setEndTime_min(startTime + newDuration);

    }

    public void assignDurationToStop(Activity activity) {

        int midnight = (activity.getDayOfWeek().ordinal()) * 24 * 60;
        int startTime = 0;
        //assumes a duration if starting in the morning - this would only be relevant if the stop was a mandatory activity, for discretionary there is probably not a differentiation of durations by start time.
        StartTimeInterval first = durationDistributionMap.get(activity.getPurpose()).keySet().stream().findFirst().get();
        int duration = durationDistributionMap.get(activity.getPurpose()).get(first).selectTime();

        activity.setStartTime_min(midnight + startTime);
        activity.setEndTime_min(midnight + startTime + duration);

    }

    @Override
    public void assignDurationAndThenStartTime(Activity activity) {

        final DayOfWeek dayOfWeek = activity.getDayOfWeek();
        int travelTime = 30; //default travel time
        int startTime;
        int initialDuration = typicalDuration.get(activity.getPurpose());

        //Select duration first
        int newDuration = durationDistributionMap.get(activity.getPurpose()).get(getInterval(8, activity.getPurpose())).selectTime();
        if (newDuration + travelTime > initialDuration) {
            //tour does not fit here! Make it shorter
            newDuration = initialDuration;
        }

        //Select start time next
        int midnight = (activity.getDayOfWeek().ordinal()) * 24 * 60;

        BlockedTimeOfWeekLinkedList blockedTimeOfWeek = activity.getPerson().getPlan().getBlockedTimeOfDay();

        TimeOfWeekDistribution timeOfWeekDistribution = timeOfWeekDistributionMap.get(activity.getPurpose());
        //newDuration = 60;
        timeOfWeekDistribution = TimeOfDayUtils.updateTODWithAvailabilityAndDuration(timeOfWeekDistribution, blockedTimeOfWeek, newDuration);
        timeOfWeekDistribution = timeOfWeekDistribution.getForThisDayOfWeek(dayOfWeek);

        if (activity.getPurpose() == Purpose.WORK && activity.getPerson().getOccupation() == Occupation.EMPLOYED
                && activity.getPerson().getSiloJobDuration() > 0) {
            newDuration = activity.getPerson().getSiloJobDuration();
            if (dayOfWeek.equals(DayOfWeek.SATURDAY) || dayOfWeek.equals(DayOfWeek.SUNDAY)) {
                startTime = activity.getPerson().getSiloJobStartTimeWeekends() + midnight;
            } else {
                startTime = activity.getPerson().getSiloJobStartTimeWorkdays() + midnight;
            }

            double startTimeProbability = timeOfWeekDistribution.probability(startTime);

            if (startTimeProbability == 0) {
                startTime = timeOfWeekDistribution.selectTime();
            }
        } else {
            startTime = timeOfWeekDistribution.selectTime();
        }

        // Setters
        activity.setStartTime_min(startTime);
        activity.setEndTime_min(startTime + newDuration);
    }
}
