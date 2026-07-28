package abm.io.input;

import abm.data.DataSet;
import abm.data.geo.MicroscopicLocation;
import abm.data.pop.Household;
import abm.data.pop.Job;
import abm.data.pop.Person;
import abm.data.pop.Relationship;
import abm.data.pop.School;
import abm.data.travelInformation.SimpleTravelDistances;
import abm.data.travelInformation.SimpleTravelTimes;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.data.person.Disability;
import de.tum.bgu.msm.data.person.Gender;
import de.tum.bgu.msm.data.person.Occupation;
import org.apache.log4j.Logger;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.HashSet;
import java.util.Map;
import java.util.Random;
import java.util.Set;

/**
 * Minimal "hello world" reader that wires a SILO (Maryland calib5) synthetic population into ABIT.
 *
 * It reads only the SILO household (hh_*.csv) and person (pp_*.csv) files, mapping SILO columns to
 * ABIT's data objects. It is meant to be paired with {@link abm.models.SimpleModelSetup}, which uses
 * dummy coefficients and constant (Simple) travel times/distances, so NO zones shapefile, OMX skims,
 * or Munich coefficient files are required. Home / job / school locations are synthesized with random
 * micro-coordinates (SILO dwelling/job coords are NULL in the output), exactly as SimpleDataReaderManager
 * does, because the Simple sub-models ignore geography beyond straight-line distance.
 */
public class MarylandDataReaderManager implements DataReaderManager {

    private static final Logger logger = Logger.getLogger(MarylandDataReaderManager.class);

    private final int maxHouseholds;
    private final Random rnd = AbitUtils.getRandomObject();

    public MarylandDataReaderManager(int maxHouseholds) {
        this.maxHouseholds = maxHouseholds;
    }

    @Override
    public DataSet readData() {
        DataSet dataSet = new DataSet();

        String hhFile = AbitResources.instance.getString("households.file");
        String ppFile = AbitResources.instance.getString("persons.file");

        Set<Integer> keptHouseholds = readHouseholds(dataSet, hhFile);
        readPersons(dataSet, ppFile, keptHouseholds);

        dataSet.setTravelTimes(new SimpleTravelTimes());
        dataSet.setTravelDistances(new SimpleTravelDistances());

        logger.info("Maryland subset loaded: households=" + dataSet.getHouseholds().size()
                + " persons=" + dataSet.getPersons().size() + " jobs=" + dataSet.getJobs().size()
                + " schools=" + dataSet.getSchools().size());
        return dataSet;
    }

    private Set<Integer> readHouseholds(DataSet dataSet, String hhFile) {
        Set<Integer> kept = new HashSet<>();
        try (BufferedReader br = new BufferedReader(new FileReader(hhFile))) {
            String[] header = br.readLine().split(",");
            int idIdx = indexOf(header, "id");
            int autosIdx = indexOf(header, "autos");
            String line;
            while ((line = br.readLine()) != null && dataSet.getHouseholds().size() < maxHouseholds) {
                String[] r = line.split(",");
                int id = Integer.parseInt(r[idIdx].trim());
                int autos = Integer.parseInt(r[autosIdx].trim());
                MicroscopicLocation home = randomLocation(30000);
                Household hh = new Household(id, home, autos);
                hh.setSimulated(Boolean.TRUE);   // printers filter on getSimulated()
                hh.setPartition(2);
                dataSet.getHouseholds().put(id, hh);
                kept.add(id);
            }
        } catch (Exception e) {
            throw new RuntimeException("Failed reading households file " + hhFile, e);
        }
        logger.info("Read " + kept.size() + " households (cap " + maxHouseholds + ")");
        return kept;
    }

    private void readPersons(DataSet dataSet, String ppFile, Set<Integer> keptHouseholds) {
        int jobSeq = 1;
        int schoolSeq = 1;
        try (BufferedReader br = new BufferedReader(new FileReader(ppFile))) {
            String[] header = br.readLine().split(",");
            int idIdx = indexOf(header, "id");
            int hhidIdx = indexOf(header, "hhid");
            int ageIdx = indexOf(header, "age");
            int genderIdx = indexOf(header, "gender");
            int relIdx = indexOf(header, "relationShip");
            int occIdx = indexOf(header, "occupation");
            int licIdx = indexOf(header, "driversLicense");
            int incIdx = indexOf(header, "income");

            Map<Integer, Household> households = dataSet.getHouseholds();
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                int hhid = Integer.parseInt(r[hhidIdx].trim());
                if (!keptHouseholds.contains(hhid)) {
                    continue;
                }
                Household hh = households.get(hhid);
                int id = Integer.parseInt(r[idIdx].trim());
                int age = Integer.parseInt(r[ageIdx].trim());
                Gender gender = Gender.valueOf(Integer.parseInt(r[genderIdx].trim()));
                Relationship relationship = Relationship.valueOf(strip(r[relIdx]));
                Occupation occupation = Occupation.valueOf(Integer.parseInt(r[occIdx].trim()));
                boolean license = Boolean.parseBoolean(r[licIdx].trim());
                int annualIncome = (int) Double.parseDouble(r[incIdx].trim());
                int monthlyIncome = annualIncome / 12;

                // Synthesize mandatory-activity anchors so PlanGenerator never dereferences a null
                // job/school. The Simple sub-models only use straight-line distance, so coords are dummy.
                Job job = null;
                School school = null;
                if (occupation == Occupation.EMPLOYED) {
                    job = new Job(jobSeq++, id, "OTH", randomLocation(30000), 8 * 60, 8 * 60);
                    dataSet.getJobs().put(job.getId(), job);
                } else if (occupation == Occupation.STUDENT) {
                    school = new School(schoolSeq++, "edu", 1, 0, randomLocation(30000), 8 * 60, 6 * 60);
                    dataSet.getSchools().put(school.getId(), school);
                }

                Person person = new Person(id, hh, age, gender, relationship, occupation, license,
                        job, 8 * 60, 8 * 60, 8 * 60, monthlyIncome, school, Disability.WITHOUT);

                hh.getPersons().add(person);
                dataSet.getPersons().put(id, person);
            }
        } catch (Exception e) {
            throw new RuntimeException("Failed reading persons file " + ppFile, e);
        }
    }

    private MicroscopicLocation randomLocation(double span) {
        return new MicroscopicLocation((rnd.nextDouble() - 0.5) * span, (rnd.nextDouble() - 0.5) * span);
    }

    private static int indexOf(String[] header, String name) {
        for (int i = 0; i < header.length; i++) {
            if (strip(header[i]).equalsIgnoreCase(name)) {
                return i;
            }
        }
        throw new RuntimeException("Column '" + name + "' not found in header");
    }

    private static String strip(String s) {
        return s.replace("\"", "").trim();
    }
}
