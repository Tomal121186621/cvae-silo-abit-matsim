package abm.models.activityGeneration.time;

import abm.data.plans.Activity;
import abm.data.plans.Purpose;
import abm.data.timeOfDay.BlockedTimeOfWeekLinkedList;
import abm.data.timeOfDay.TimeOfDayUtils;
import abm.data.timeOfDay.TimeOfWeekDistribution;
import de.tum.bgu.msm.util.MitoUtil;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.time.DayOfWeek;
import java.util.HashMap;
import java.util.Map;

public class SimpleTimeAssignmentWithTimeAvailability implements TimeAssignment {


    private Map<Purpose, TimeOfWeekDistribution> timeOfWeekDistributionMap;

    public SimpleTimeAssignmentWithTimeAvailability() {
        timeOfWeekDistributionMap = new HashMap<>();
        readTimeOfDayDistributions();
    }

    private void readTimeOfDayDistributions() {

        int timeIndex;
        int purposeIndex;
        int probabilityIndex;

        try {
            String todFile = abm.properties.AbitResources.instance != null
                    ? abm.properties.AbitResources.instance.getString("tod.dummy.file")
                    : null;
            if (todFile == null) {
                todFile = "input/tod_dummy.csv";
            }
            BufferedReader br = new BufferedReader(new FileReader(todFile));
            String[] firstLine = br.readLine().split(",");

            timeIndex = MitoUtil.findPositionInArray("time", firstLine);
            purposeIndex = MitoUtil.findPositionInArray("purpose", firstLine);
            probabilityIndex = MitoUtil.findPositionInArray("probability", firstLine);

            String line;
            while((line = br.readLine())!= null){
                int time = Integer.parseInt(line.split(",")[timeIndex]);
                Purpose purpose = Purpose.valueOf(line.split(",")[purposeIndex]);
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

        //define duration
        int duration = 100;

        //add travel to duration
        duration += 2 * 30;

        //get the available time for new tours
        BlockedTimeOfWeekLinkedList availableTimeOfWeek = activity.getPerson().getPlan().getBlockedTimeOfDay();
        availableTimeOfWeek = TimeOfDayUtils.updateAvailableTimeForNextTrip(availableTimeOfWeek, duration);
        availableTimeOfWeek = availableTimeOfWeek.getForThisDayOfWeek(dayOfWeek);


        //get the departure probabilities
        TimeOfWeekDistribution timeOfWeekDistribution = timeOfWeekDistributionMap.get(activity.getPurpose());

        //convert to the selected day
        timeOfWeekDistribution = timeOfWeekDistribution.getForThisDayOfWeek(dayOfWeek);

        //update the probabilities with the availability and expected tour duration
        timeOfWeekDistribution = TimeOfDayUtils.updateTODWithAvailability(timeOfWeekDistribution, availableTimeOfWeek);


        int startTime;
        startTime = timeOfWeekDistribution.selectTime();

        //int midnight = (activity.getDayOfWeek().getValue() - 1) * 24 * 3600/60;

        activity.setStartTime_min(startTime);
        activity.setEndTime_min(startTime + duration);

    }

    public void assignDurationToStop(Activity activity) {

        int midnight = (activity.getDayOfWeek().ordinal()) * 24*60 ;
        int startTime = 0;
        int duration;

        switch (activity.getPurpose()){
            case ACCOMPANY:
                duration = 30;
                break;
            case SHOPPING:
                duration = 20;
                break;
            case OTHER:
                duration = 5;
                break;
            case RECREATION:
                duration = 120;
                break;
            default:
                throw new RuntimeException("Error assigning stop duration to a non-compatible purpose");
        }

        activity.setStartTime_min(midnight + startTime);
        activity.setEndTime_min(midnight + startTime + duration);

    }

    @Override
    public void assignDurationAndThenStartTime(Activity activity) {

    }
}
