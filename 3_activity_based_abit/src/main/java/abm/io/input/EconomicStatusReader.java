package abm.io.input;

import abm.data.DataSet;
import abm.data.pop.EconomicStatus;
import abm.data.pop.Household;
import abm.data.pop.Person;
import de.tum.bgu.msm.util.MitoUtil;
import org.apache.log4j.Logger;

import java.util.HashMap;
import java.util.Map;

public class EconomicStatusReader implements Reader{
    private static final Logger logger = Logger.getLogger(EconomicStatusReader.class);
    private final DataSet dataSet;
    private Map<EconomicStatus, Integer> economicStatusMap = new HashMap<>();

    public EconomicStatusReader(DataSet dataSet){
        this.dataSet = dataSet;
        economicStatusMap.put(EconomicStatus.from0to800, 0);
        economicStatusMap.put(EconomicStatus.from801to1600, 0);
        economicStatusMap.put(EconomicStatus.from1601to2400, 0);
        economicStatusMap.put(EconomicStatus.from2401, 0);
    }

    @Override
    public void read() {

        for (Household household: this.dataSet.getHouseholds().values()){

            double avgPerson;
            double income = 0;
            int countAdult = 0;
            int countChild = 0;

            for (Person person : household.getPersons()){
                income += person.getMonthlyIncome_eur();
                if (person.getAge() >= 14){
                    countAdult += 1;
                }
                if (person.getAge() < 14){
                    countChild += 1;
                }
            }

            avgPerson = MitoUtil.rounder(Math.min(3.5f, 1.0f + (countAdult - 1f) * 0.5f + countChild * 0.3f), 1);

            double EurPerAdjPerson = income / avgPerson;

            if (EurPerAdjPerson <= 800.0){
                household.setEconomicStatus(EconomicStatus.from0to800);
                economicStatusMap.put(EconomicStatus.from0to800, economicStatusMap.get(EconomicStatus.from0to800) +1);
            } else if (EurPerAdjPerson <= 1600.0){
                household.setEconomicStatus(EconomicStatus.from801to1600);
                economicStatusMap.put(EconomicStatus.from801to1600, economicStatusMap.get(EconomicStatus.from801to1600) +1);
            } else if(EurPerAdjPerson <= 2400.0){
                household.setEconomicStatus(EconomicStatus.from1601to2400);
                economicStatusMap.put(EconomicStatus.from1601to2400, economicStatusMap.get(EconomicStatus.from1601to2400) +1);
            }else{
                household.setEconomicStatus(EconomicStatus.from2401);
                economicStatusMap.put(EconomicStatus.from2401, economicStatusMap.get(EconomicStatus.from2401) +1);
            }
        }

        for (EconomicStatus economicStatus:economicStatusMap.keySet()){
            logger.info(economicStatus.toString() + " has " + economicStatusMap.get(economicStatus));
        }
    }
}
