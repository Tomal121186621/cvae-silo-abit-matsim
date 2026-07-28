package abm.models.activityGeneration.splitByType;

import abm.data.DataSet;
import abm.data.plans.*;
import abm.data.timeOfDay.BlockedTimeOfWeekLinkedList;
import abm.data.timeOfDay.TimeOfWeekDistribution;
import abm.properties.AbitResources;
import abm.properties.InternalProperties;
import abm.utils.AbitUtils;
import abm.data.pop.Person;
import de.tum.bgu.msm.util.MitoUtil;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.time.DayOfWeek;
import java.util.HashMap;
import java.util.Map;

public class SplitStopByTypeModel implements SplitStopType {

    private int counterErrors = 0;
    private final Map<Purpose, TimeOfWeekDistribution> timeOfWeekDistributionMap;
    private boolean runCalibration = false;

    public SplitStopByTypeModel() {
        timeOfWeekDistributionMap = new HashMap<>();
        readTimeOfDayDistributions();
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
    public StopType getStopType(Person person, Activity activity, Tour tour) {

        BlockedTimeOfWeekLinkedList availableTimeOfDay = person.getPlan().getBlockedTimeOfDay();

        final DayOfWeek dayOfWeek = tour.getMainActivity().getDayOfWeek();
        int midnight = dayOfWeek.ordinal() * 24 * 60;

        availableTimeOfDay = availableTimeOfDay.getForThisDayOfWeek(dayOfWeek);

        int tourStart_min = tour.getLegs().firstKey();
        Leg lastLeg = tour.getLegs().get(tour.getLegs().lastKey());
        int tourEnd_min = tour.getLegs().lastKey() + lastLeg.getTravelTime_min();


        //count periods before
        int nBefore = 0;
        double pBefore = 0;
        for (int t = tourStart_min - InternalProperties.SEARCH_INTERVAL_MIN; t > midnight; t = t - InternalProperties.SEARCH_INTERVAL_MIN) {
            if (availableTimeOfDay.isAvailable(t) == 1) {
                nBefore++;
                pBefore += timeOfWeekDistributionMap.get(activity.getPurpose()).probability(t);
            } else {
                //until it finds the previous blocked time
                break;
            }
        }
        double travelTimeBefore_min = tour.getLegs().get(tour.getLegs().firstKey()).getTravelTime_min() * 2; //approximation

        //count periods after
        int nAfter = 0;
        double pAfter = 0;
        for (int t = tourEnd_min + InternalProperties.SEARCH_INTERVAL_MIN; t < midnight + 60 * 24; t += InternalProperties.SEARCH_INTERVAL_MIN) {
            if (availableTimeOfDay.isAvailable(t) == 1) {
                nAfter++;
                pAfter += timeOfWeekDistributionMap.get(activity.getPurpose()).probability(t);
            } else {
                //until it finds the next blocked time
                break;
            }
        }
        double travelTimeAfter_min = lastLeg.getTravelTime_min() * 2; //approximation


        final int searchIntervalMin = InternalProperties.SEARCH_INTERVAL_MIN;
        final int duration = activity.getDuration();
        if (nAfter * searchIntervalMin > duration + travelTimeAfter_min && nBefore * searchIntervalMin > duration + travelTimeBefore_min) {
            double probabilityBefore = pBefore / (pBefore + pAfter);
            if (AbitUtils.randomObject.nextDouble() < probabilityBefore) {
                return StopType.BEFORE;
            } else {
                return StopType.AFTER;
            }

        } else if (nAfter * searchIntervalMin > duration + travelTimeAfter_min) {
            return StopType.AFTER;
        } else if (nBefore * searchIntervalMin > duration + travelTimeBefore_min) {
            return StopType.BEFORE;
        } else {
            counterErrors++;
            //System.out.println("Cannot allocate this stop: n = " + counterErrors);
            return null;
        }


    }

}
