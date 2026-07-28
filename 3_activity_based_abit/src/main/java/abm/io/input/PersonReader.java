package abm.io.input;

import abm.data.DataSet;
import abm.data.pop.*;
import abm.properties.AbitResources;
import de.tum.bgu.msm.data.person.Disability;
import de.tum.bgu.msm.data.person.Gender;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.util.MitoUtil;
import org.apache.log4j.Logger;

import java.io.BufferedReader;

import java.io.FileReader;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

public class PersonReader implements Reader {

    private final DataSet dataSet;
    private final Map<String, Integer>  indexes;
    final String path;
    private BufferedReader br;

    final static String REGEX = ",";
    private Logger logger = Logger.getLogger(PersonReader.class);

    public PersonReader(DataSet dataSet) {
        this.dataSet = dataSet;
        indexes = new HashMap<>();
        path = AbitResources.instance.getString("persons.file");
    }

    @Override
    public void read() {
        try {
            br = new BufferedReader(new FileReader(path));
            logger.info("Reading from " + path);
            processHeader(br, indexes);
            processRecords(br, indexes, dataSet);
        } catch (IOException e) {
            e.printStackTrace();
        }

    }

    private void processHeader(BufferedReader br, Map<String, Integer>  indexes) throws IOException {
        String[] header = br.readLine().split(REGEX);

        indexes.put("id", MitoUtil.findPositionInArray("id", header));
        indexes.put("hhid", MitoUtil.findPositionInArray("hhid", header));
        indexes.put("age", MitoUtil.findPositionInArray("age", header));
        indexes.put("gender", MitoUtil.findPositionInArray("gender", header));
        indexes.put("relationship", MitoUtil.findPositionInArray("relationShip", header));
        indexes.put("occupation", MitoUtil.findPositionInArray("occupation", header));
        indexes.put("driversLicense", MitoUtil.findPositionInArray("driversLicense", header));
        indexes.put("workplace", MitoUtil.findPositionInArray("workplace", header));
        indexes.put("income", MitoUtil.findPositionInArray("income", header));
        indexes.put("schoolplace", MitoUtil.findPositionInArray("schoolId", header));
        indexes.put("disability", MitoUtil.findPositionInArray("disability", header));
        indexes.put("employmentStatus", MitoUtil.findPositionInArray("jobType", header));
        indexes.put("jobDuration", MitoUtil.findPositionInArray("jobDuration", header));
        indexes.put("jobStartTimeWorkdays", MitoUtil.findPositionInArray("jobStartTimeWorkdays", header));
        indexes.put("jobStartTimeWeekends", MitoUtil.findPositionInArray("jobStartTimeWeekends", header));
    }


    private void processRecords(BufferedReader br, Map<String, Integer>  indexes, DataSet dataSet) throws IOException {

        String line;
        while ((line = br.readLine())!= null){

            String[] splitLine = line.split(REGEX);

            int id = Integer.parseInt(splitLine[indexes.get("id")]);
            int hhid = Integer.parseInt(splitLine[indexes.get("hhid")]);

            Household hh = dataSet.getHouseholds().getOrDefault(hhid, null);

            if (hh == null){
                throw new RuntimeException("The household does not exist");
            }


            int age = Integer.parseInt(splitLine[indexes.get("age")]);
            Gender gender = Gender.valueOf(Integer.parseInt(splitLine[indexes.get("gender")]));
            Relationship relationship = Relationship.valueOf(splitLine[indexes.get("relationship")].replace("\"",""));
            Occupation occupation = Occupation.valueOf(Integer.parseInt(splitLine[indexes.get("occupation")]));
            boolean hasLicense = Boolean.parseBoolean(splitLine[indexes.get("driversLicense")]);
            Disability disability = Disability.valueOf(splitLine[indexes.get("disability")]);
            String employmentStatus = splitLine[indexes.get("employmentStatus")];

            int jobId = Integer.parseInt(splitLine[indexes.get("workplace")]);
            Job jj = null;
            if (jobId != 0){
                jj = dataSet.getJobs().getOrDefault(jobId, null);
            }

            int income = Integer.parseInt(splitLine[indexes.get("income")])/12;

            int jobDuration = Integer.parseInt(splitLine[indexes.get("jobDuration")]);

            int jobStartTimeWorkdays = Integer.parseInt(splitLine[indexes.get("jobStartTimeWorkdays")]);

            int jobStartTimeWeekends = Integer.parseInt(splitLine[indexes.get("jobStartTimeWeekends")]);

            int schoolId = Integer.parseInt(splitLine[indexes.get("schoolplace")]);

            School school = null;
            if (schoolId != 0){
                school = dataSet.getSchools().getOrDefault(schoolId, null);
            }

            Person person = new Person(id, hh, age, gender, relationship, occupation, hasLicense, jj, jobDuration,jobStartTimeWorkdays,
                    jobStartTimeWeekends, income, school, disability);

            if (employmentStatus.equals("fullTime")){
                person.setEmploymentStatus(EmploymentStatus.FULLTIME_EMPLOYED);
            }else if(employmentStatus.equals("partTime")){
                person.setEmploymentStatus(EmploymentStatus.HALFTIME_EMPLOYED);
            }else{
                person.setEmploymentStatus(EmploymentStatus.NO_INFO);
            }



            hh.getPersons().add(person);

            if (jj != null){
                jj.setPerson(person);
            }

            dataSet.getPersons().put(id, person);


        }

    }
}
