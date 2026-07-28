package abm.data.timeOfDay;

import abm.properties.InternalProperties;
import de.tum.bgu.msm.util.MitoUtil;

import java.time.DayOfWeek;
import java.util.List;
import java.util.SortedMap;
import java.util.TreeMap;
import java.util.stream.Collectors;


/**
 * Defines the probability distribution of starting a trip or of the duration of a trip.
 * Defined by a map with key the starting time of the time window and valua a double indicating probability
 */
public class DurationDistribution {

    private SortedMap<Integer, Double> internalMap;
    private static final int MAX_VALUE = (int) (24 * 60);


    public DurationDistribution() {
        internalMap = new TreeMap<>();
        for (int i = 0; i < MAX_VALUE; i = i+InternalProperties.SEARCH_INTERVAL_MIN) {
            internalMap.put(i, 0.);
        }
    }

    public void setProbability(int minute, double probability) {
        if (internalMap.containsKey(minute)) {
            internalMap.put(minute, probability);
        } else {

        }
    }


    public double probability(int minute) {
        if (internalMap.containsKey(minute)) {
            return internalMap.get(minute);
        } else {
            int newIndex = Math.round(minute/ InternalProperties.SEARCH_INTERVAL_MIN) * InternalProperties.SEARCH_INTERVAL_MIN;
            return internalMap.get(newIndex);
        }


    }

    public int selectTime() {
        if (MitoUtil.getSum(internalMap.values()) > 0){
            return MitoUtil.select(internalMap);
        } else {
            return -1;
        }
    }

    public List<Integer> getMinutes() {
        return internalMap.keySet().stream().collect(Collectors.toList());
    }



}
