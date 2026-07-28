package abm.data.timeOfDay;

import abm.data.vehicle.Car;
import abm.properties.InternalProperties;

import java.time.DayOfWeek;
import java.util.ArrayList;
import java.util.List;
import java.util.SortedMap;
import java.util.TreeMap;


/**
This class defines a map of availability, with a key start time in minutes of the time window and a value boolean that defines
if the window is available (true) or not (false)
 **/

public class AvailableTimeOfWeek {



    private SortedMap<Integer, Boolean> internalMap;
    private static final int MAX_VALUE = (int) (7 * 24 * 60 );


    public AvailableTimeOfWeek() {
        internalMap = new TreeMap<>();
        for (int i = 0; i < MAX_VALUE; i = i + InternalProperties.SEARCH_INTERVAL_MIN) {
            internalMap.put(i, true);
        }
    }

    public void blockTime(int from, int until) {
        for (int i = 0; i < MAX_VALUE; i = i + InternalProperties.SEARCH_INTERVAL_MIN) {
            if (i >= from && i <= until) {
                internalMap.put(i, false);
            }
        }
    }

    public int isAvailable(int minute) {
        if (internalMap.containsKey(minute)) {
            return internalMap.get(minute) ? 1 : 0;
        } else {
            int newIndex = Math.round(minute/InternalProperties.SEARCH_INTERVAL_MIN) * InternalProperties.SEARCH_INTERVAL_MIN;
            return internalMap.get(newIndex) ? 1 : 0;
        }
    }

    public boolean isAvailable(int startMinute, int endMinute) {

        for (int minute = startMinute; minute <= endMinute; minute++) {
            if (internalMap.containsKey(minute)) {
                if(!internalMap.get(minute)){
                    return Boolean.FALSE;
                }
            } else {
                int newIndex = Math.round(minute/InternalProperties.SEARCH_INTERVAL_MIN) * InternalProperties.SEARCH_INTERVAL_MIN;
                if(!internalMap.get(newIndex)){
                    return Boolean.FALSE;
                }
            }
        }

        return Boolean.TRUE;
    }

    public List<Integer> getMinutes() {
        return new ArrayList<>(internalMap.keySet());
    }


    public AvailableTimeOfWeek getForThisDayOfWeek(DayOfWeek dayOfWeek){
        int midnightBefore = (dayOfWeek.ordinal()) * 24*60;
        AvailableTimeOfWeek availableTimeOfDay = new AvailableTimeOfWeek();
        this.internalMap.keySet().forEach(m ->{
            if (m > midnightBefore && m < midnightBefore + 60 * 24){
                if(this.internalMap.get(m)){
                    availableTimeOfDay.internalMap.put(m, true);
                } else {
                    availableTimeOfDay.internalMap.put(m, false);
                }
            } else {
                availableTimeOfDay.internalMap.put(m, false);
            }
        });

        return availableTimeOfDay;
    }


    /*@Override
    public String toString() {
        StringBuilder value =  new StringBuilder();
        internalMap.values().forEach(v-> value.append(v?1:0));
        return value.toString();
    }*/

    public SortedMap<Integer, Boolean> getInternalMap() {
        return internalMap;
    }
}
