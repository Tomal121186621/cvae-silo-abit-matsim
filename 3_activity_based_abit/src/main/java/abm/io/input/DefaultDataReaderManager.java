package abm.io.input;

import abm.data.DataSet;
import abm.data.geo.Zone;
import abm.data.pop.Household;
import abm.data.pop.Job;
import abm.data.pop.Person;
import de.tum.bgu.msm.data.person.Occupation;

import java.util.HashMap;
import java.util.Map;

public class DefaultDataReaderManager implements DataReaderManager {
    @Override
    public DataSet readData() {
        DataSet dataSet = new DataSet();
        new ZoneReader(dataSet).read();
        new MitoTravelTimeAndDistanceReader(dataSet).read();

        new HouseholdReader(dataSet).read();
        new VehicleReader(dataSet).read();
        new JobReader(dataSet).read();
        new SchoolReader(dataSet).read();
        new PersonReader(dataSet).read();
        populateZones(dataSet);
        new EconomicStatusReader(dataSet).read();
        new CalibrationZoneToRegionTypeReader(dataSet).read();

        return dataSet;
    }

    private void populateZones(DataSet dataSet) {

        String[] keys = new String[]{"hh.total","jj.total","jj.retail","jj.office","jj.other","students"};
        Map<Zone, Map<String, Integer>> zoneAttractors = new HashMap<>();

        for (Zone zone : dataSet.getZones().values()) {
            zoneAttractors.putIfAbsent(zone, new HashMap<>());
            for (String key : keys) {
                zoneAttractors.get(zone).putIfAbsent(key, 0);
            }
        }
        for (Household household : dataSet.getHouseholds().values()) {
            Zone zone = dataSet.getZones().get(household.getLocation().getZoneId());
            zoneAttractors.get(zone).put("hh.total", zoneAttractors.get(zone).get("hh.total") + household.getPersons().size());
            for (Person pp: household.getPersons()){
                if (pp.getOccupation().equals(Occupation.STUDENT)) {
                    Zone schoolZone = dataSet.getZones().get(pp.getSchool().getLocation().getZoneId());
                    zoneAttractors.get(schoolZone).put("students", zoneAttractors.get(schoolZone).get("students") + 1);
                }
            }
        }
        for (Job job : dataSet.getJobs().values()){
            Zone zone = dataSet.getZones().get(job.getLocation().getZoneId());
            zoneAttractors.get(zone).put("jj.total", zoneAttractors.get(zone).get("jj.total") + 1);
            if (job.getType().equals("Retl")){
                zoneAttractors.get(zone).put("jj.retail", zoneAttractors.get(zone).get("jj.retail") + 1);
            } else if (job.getType().equals("Finc") || job.getType().equals("Rlst") || job.getType().equals("Admn") || job.getType().equals("Serv")){
                zoneAttractors.get(zone).put("jj.office", zoneAttractors.get(zone).get("jj.office") + 1);
            } else {
                zoneAttractors.get(zone).put("jj.other", zoneAttractors.get(zone).get("jj.other") + 1);
            }
        }

        for (Zone zone : dataSet.getZones().values()) {
            for (String key : keys) {
                zone.setAttribute(key, zoneAttractors.get(zone).get(key));
            }
        }

    }


}
