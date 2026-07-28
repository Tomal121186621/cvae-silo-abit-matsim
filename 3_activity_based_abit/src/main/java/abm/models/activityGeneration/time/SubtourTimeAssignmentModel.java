package abm.models.activityGeneration.time;

import abm.data.DataSet;
import abm.data.plans.Activity;
import abm.data.plans.Purpose;
import abm.data.timeOfDay.DurationDistribution;
import abm.data.timeOfDay.TimeOfWeekDistribution;
import abm.models.activityGeneration.frequency.SubtourGeneratorModel;
import abm.properties.AbitResources;
import de.tum.bgu.msm.util.MitoUtil;
import ncsa.hdf.object.Dataset;
import org.apache.log4j.Logger;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class SubtourTimeAssignmentModel implements SubtourTimeAssignment{

    private static final Logger logger = Logger.getLogger(SubtourTimeAssignmentModel.class);

    private final DataSet dataSet;

    private final Map<Integer, Double> startTimeDurationMap;
    private final Map<Integer, Double> durationDistributionMap;


    public SubtourTimeAssignmentModel(DataSet dataSet){
        this.dataSet = dataSet;

        startTimeDurationMap = new HashMap<>();
        durationDistributionMap = new HashMap<>();

        readStartTimeDuration();
        readDurationDistribution();

    }

    private void readStartTimeDuration(){
        int timeIndex;
        int probabilityIndex;

        try {
            BufferedReader br = new BufferedReader(new FileReader(AbitResources.instance.getString("start.time.subtour")));
            String[] firstLine = br.readLine().split(",");

            timeIndex = MitoUtil.findPositionInArray("min", firstLine);
            probabilityIndex = MitoUtil.findPositionInArray("startTimeProbability", firstLine);

            String line;
            while((line = br.readLine())!= null){
                int time = Integer.parseInt(line.split(",")[timeIndex]);
                double probability = Double.parseDouble(line.split(",")[probabilityIndex]);
                startTimeDurationMap.put(time, probability);
            }

        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private void readDurationDistribution(){
        int durationIndex;
        int probabilityIndex;

        try {
            BufferedReader br = new BufferedReader(new FileReader(AbitResources.instance.getString("act.duration.subtour")));
            String[] firstLine = br.readLine().split(",");

            durationIndex = MitoUtil.findPositionInArray("min", firstLine);
            probabilityIndex = MitoUtil.findPositionInArray("actDurationProbability", firstLine);

            String line;
            while((line = br.readLine())!= null){
                int duration = Integer.parseInt(line.split(",")[durationIndex]);
                double probability = Double.parseDouble(line.split(",")[probabilityIndex]);
                durationDistributionMap.put(duration, probability);
            }

        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    @Override
    public void assignTimeToSubtourActivity(Activity subtourActivity, Activity mainActivity) {
        subtourActivity.setDayOfWeek(mainActivity.getDayOfWeek());

        int startTime = calculateStartTime(mainActivity);
        subtourActivity.setStartTime_min(startTime);

        int duration = calculateDuration();
        subtourActivity.setEndTime_min(subtourActivity.getStartTime_min() + duration);

    }

    private int calculateDuration(){
        int duration = MitoUtil.select(durationDistributionMap);
        return duration;
    }

    private int calculateStartTime(Activity mainActivity){

        int dayOfWeekOffset = (mainActivity.getDayOfWeek().getValue() - 1) * 60 * 24;
        int startTime = mainActivity.getStartTime_min() - dayOfWeekOffset;
        int endTime = mainActivity.getEndTime_min() - dayOfWeekOffset;
        Map<Integer, Double> probabilityMap = new ConcurrentHashMap<>();

        for (Integer times: startTimeDurationMap.keySet()){
            if (times >= startTime && times <= endTime){
                probabilityMap.put(times, startTimeDurationMap.get(times));
            }
        }

        try{
            MitoUtil.select(probabilityMap).equals(null);
        }catch (Exception e){
            System.out.println("Error here");
        }



        if (MitoUtil.select(probabilityMap).equals(null)){
            System.out.println("!");
        }
        int selectedTimes = MitoUtil.select(probabilityMap) + dayOfWeekOffset;

        return selectedTimes;
    }


}
