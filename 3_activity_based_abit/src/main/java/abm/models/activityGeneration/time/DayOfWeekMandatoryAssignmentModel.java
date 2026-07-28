package abm.models.activityGeneration.time;

import abm.data.DataSet;
import abm.data.plans.Purpose;
import abm.data.pop.EconomicStatus;
import abm.data.pop.Person;
import abm.data.timeOfDay.TimeOfDayUtils;
import abm.data.timeOfDay.TimeOfWeekDistribution;
import abm.properties.AbitResources;
import de.tum.bgu.msm.util.MitoUtil;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.time.DayOfWeek;
import java.util.HashMap;
import java.util.Map;

public class DayOfWeekMandatoryAssignmentModel implements DayOfWeekMandatoryAssignment {

    private final DataSet dataSet;
    private final Map<Purpose, Map<EconomicStatus, Map<DayOfWeek, Double>>> dayProbabilitiesByMainActs;

    public DayOfWeekMandatoryAssignmentModel(DataSet dataSet) {
        this.dataSet = dataSet;
        dayProbabilitiesByMainActs = new HashMap<>();
        readDayOfWeekDistributionForMainActs();
    }

    private void readDayOfWeekDistributionForMainActs() {

        int purposeIndex;
        int econStatusIndex;
        int dayOfWeekIndex;
        int probabilityIndex;

        try {
            BufferedReader br = new BufferedReader(new FileReader(AbitResources.instance.getString("day.of.week.distribution.mandatory.acts")));
            String[] firstLine = br.readLine().split(",");

            purposeIndex = MitoUtil.findPositionInArray("purpose", firstLine);
            econStatusIndex = MitoUtil.findPositionInArray("econStatus", firstLine);
            dayOfWeekIndex = MitoUtil.findPositionInArray("dayOfWeek", firstLine);
            probabilityIndex = MitoUtil.findPositionInArray("probabilities", firstLine);

            String line;
            while((line = br.readLine())!= null){

                Purpose purpose = Purpose.valueOf(line.split(",")[purposeIndex].toUpperCase());
                EconomicStatus econStatus = EconomicStatus.of(Integer.parseInt(line.split(",")[econStatusIndex]));
                DayOfWeek timeOfDay = DayOfWeek.valueOf(line.split(",")[dayOfWeekIndex].toUpperCase());
                double probability = Double.parseDouble(line.split(",")[probabilityIndex]);

                dayProbabilitiesByMainActs.putIfAbsent(purpose, new HashMap<>());
                dayProbabilitiesByMainActs.get(purpose).putIfAbsent(econStatus, new HashMap<>());
                dayProbabilitiesByMainActs.get(purpose).get(econStatus).putIfAbsent(timeOfDay, probability);
            }

        } catch (IOException e) {
            e.printStackTrace();
        }


    }

    @Override
    public DayOfWeek[] assignDaysOfWeek(int numberOfDaysOfWeek, Purpose purpose, Person person) {

        Map<DayOfWeek, Double> dayProbabilities = new HashMap<>(dayProbabilitiesByMainActs.get(purpose).get(person.getHousehold().getEconomicStatus()));

        DayOfWeek[] daysOfWeek = new DayOfWeek[numberOfDaysOfWeek];

        for (int i = 0; i < numberOfDaysOfWeek; i++) {
            final DayOfWeek select = MitoUtil.select(dayProbabilities);
            daysOfWeek[i] = select;
            dayProbabilities.remove(select);
        }
        return daysOfWeek;
    }
}
