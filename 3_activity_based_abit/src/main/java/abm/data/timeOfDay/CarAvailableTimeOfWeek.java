package abm.data.timeOfDay;

import abm.properties.InternalProperties;
import cern.colt.map.tint.OpenIntIntHashMap;

import java.time.DayOfWeek;
import java.util.ArrayList;
import java.util.List;


/**
This class defines a map of availability, with a key start time in minutes of the time window and a value boolean that defines
if the window is available (true) or not (false)
 **/

public class CarAvailableTimeOfWeek {


    private OpenIntIntHashMap internalMap;
    private static final int MAX_VALUE = (int) (7 * 24 * 60 );



    public CarAvailableTimeOfWeek() {
        internalMap = new OpenIntIntHashMap();
        for (int i = 0; i < MAX_VALUE; i = i + InternalProperties.SEARCH_INTERVAL_MIN) {
            internalMap.put(i, 1);
        }
    }

    public void blockTime(int from, int until) {
        for (int i = 0; i < MAX_VALUE; i = i + InternalProperties.SEARCH_INTERVAL_MIN) {
            if (i >= from && i <= until) {
                internalMap.put(i, 0);
            }
        }
    }

    public int isAvailable(int minute) {
        if (internalMap.containsKey(minute)) {
            return internalMap.get(minute);
        } else {
            int newIndex = Math.round(minute/InternalProperties.SEARCH_INTERVAL_MIN) * InternalProperties.SEARCH_INTERVAL_MIN;
            return internalMap.get(newIndex);
        }
    }

    public boolean isAvailable(int startMinute, int endMinute) {

        for (int minute = startMinute; minute <= endMinute; minute++) {
            if (internalMap.containsKey(minute)) {
                if(internalMap.get(minute) == 0){
                    return Boolean.FALSE;
                }
            } else {
                int newIndex = Math.round(minute/InternalProperties.SEARCH_INTERVAL_MIN) * InternalProperties.SEARCH_INTERVAL_MIN;
                if(internalMap.get(newIndex) == 0){
                    return Boolean.FALSE;
                }
            }
        }

        return Boolean.TRUE;
    }

    public List<Integer> getMinutes() {
        return new ArrayList<>(internalMap.keys().toList());
    }


    public CarAvailableTimeOfWeek getForThisDayOfWeek(DayOfWeek dayOfWeek){
        int midnightBefore = (dayOfWeek.ordinal()) * 24*60;
        CarAvailableTimeOfWeek availableTimeOfDay = new CarAvailableTimeOfWeek();
        this.internalMap.keys().forEach(m ->{
            if (m > midnightBefore && m < midnightBefore + 60 * 24){
                if(this.internalMap.get(m) == 1){
                    availableTimeOfDay.internalMap.put(m, 1);
                } else {
                    availableTimeOfDay.internalMap.put(m, 0);
                }
            } else {
                availableTimeOfDay.internalMap.put(m, 0);
            }
            return true;
        });

        return availableTimeOfDay;
    }


    /*@Override
    public String toString() {
        StringBuilder value =  new StringBuilder();
        internalMap.values().forEach(v-> value.append(v?1:0));
        return value.toString();
    }*/

    public OpenIntIntHashMap getInternalMap() {
        return internalMap;
    }
}
