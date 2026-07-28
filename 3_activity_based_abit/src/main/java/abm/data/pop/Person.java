package abm.data.pop;

import abm.data.plans.*;
import de.tum.bgu.msm.data.person.Disability;
import de.tum.bgu.msm.data.person.Gender;
import de.tum.bgu.msm.data.person.Occupation;
import org.matsim.utils.objectattributes.attributable.Attributes;

import java.util.Optional;

public class Person {

    private final int id;
    private final Household household;
    private HabitualMode habitualMode;
    private double habitualModeGcCarD;
    private double habitualModeGcCarP;
    private double habitualModeGcPT;



    private double habitualModeBike;
    private double habitualModeWalk;

    private int age;

    private Gender gender;
    private Relationship relationship;
    private Occupation occupation;
    private boolean hasLicense;
    private Job job;
    private int siloJobDuration;
    private int siloJobStartTimeWorkdays;
    private int siloJobStartTimeWeekends;
    private int monthlyIncome_eur;
    private School school;

    private Disability disability;

    private int jobDuration;
    private int jobStartTimeWorkdays;
    private int jobStartTimeWeekends;


    private String employmentType;
    private final Attributes attributes = new Attributes();
    private Plan plan;

    private boolean bikeOwnership;


    private EmploymentStatus employmentStatus;

    //    public Person(int id, Household household) {
//        this.id = id;
//        this.household = household;
//    }
    public Person(int id, Household household, int age, Gender gender, Relationship relationship, Occupation occupation,
                  boolean hasLicense, Job job, int siloJobDuration, int siloJobStartTimeWorkdays, int siloJobStartTimeWeekends,
                  int monthlyIncome_eur, School school, Disability disability) {
        this.id = id;
        this.household = household;
        this.age = age;
        this.gender = gender;
        this.relationship = relationship;
        this.occupation = occupation;
        this.hasLicense = hasLicense;
        this.job = job;
        this.siloJobDuration = siloJobDuration;
        this.siloJobStartTimeWorkdays = siloJobStartTimeWorkdays;
        this.siloJobStartTimeWeekends = siloJobStartTimeWeekends;
        this.monthlyIncome_eur = monthlyIncome_eur;
        this.school = school;
        this.disability = disability;
    }

    public int getAge() {
        return age;
    }

    public Gender getGender() {
        return gender;
    }

    public Relationship getRelationship() {
        return relationship;
    }

    public Occupation getOccupation() {
        return occupation;
    }

    public boolean isHasLicense() {
        return hasLicense;
    }

    public Job getJob() {
        return job;
    }

    public int getSiloJobDuration() {
        return siloJobDuration;
    }

    public int getSiloJobStartTimeWorkdays() {
        return siloJobStartTimeWorkdays;
    }

    public int getSiloJobStartTimeWeekends() {
        return siloJobStartTimeWeekends;
    }

    public int getMonthlyIncome_eur() {
        return monthlyIncome_eur;
    }

    public School getSchool() {
        return school;
    }

    public Attributes getAttributes() {
        return attributes;
    }

    public int getId() {
        return id;
    }

    public Household getHousehold() {
        return household;
    }

    public HabitualMode getHabitualMode() {
        return habitualMode;
    }

    public void setHabitualMode(HabitualMode habitualMode) {
        this.habitualMode = habitualMode;
    }

    public Plan getPlan() {
        return plan;
    }

    public void setPlan(Plan plan) {
        this.plan = plan;
    }

    public Optional<Object> getAttribute(String key) {
        return Optional.ofNullable(attributes.getAttribute(key));
    }

    public void setAttribute(String key, Object value) {
        attributes.putAttribute(key, value);
    }


    public boolean hasBicycle() {
        return bikeOwnership;
    }

    public void setHasBicycle(boolean bikeOwnership) {
        this.bikeOwnership = bikeOwnership;
    }

    public Disability getDisability() {
        return disability;
    }

    public boolean hasWorkActivity() {
        for (Tour tour : plan.getTours().values()) {
            if (tour.getMainActivity().getPurpose().equals(Purpose.WORK)) {
                return true;
            }
        }

        return false;
    }

    public EmploymentStatus getEmploymentStatus() {
        return employmentStatus;
    }

    public void setEmploymentStatus(EmploymentStatus employmentStatus) {
        this.employmentStatus = employmentStatus;
    }

    public String getEmploymentType() {
        return employmentType;
    }

    public void setEmploymentType(String employmentType) {
        this.employmentType = employmentType;
    }

    public int getJobDuration() {
        return jobDuration;
    }

    public void setJobDuration() {
        this.jobDuration = jobDuration;
    }

    public int getJobStartTimeWorkdays() {
        return jobStartTimeWorkdays;
    }

    public void setJobStartTimeWorkdays() {
        this.jobStartTimeWorkdays = jobStartTimeWorkdays;
    }

    public int getJobStartTimeWeekends() {
        return jobStartTimeWeekends;
    }

    public void setJobStartTimeWeekends() {
        this.jobStartTimeWeekends = jobStartTimeWeekends;
    }

    public double getHabitualModeGcCarD() {
        return habitualModeGcCarD;
    }

    public void setHabitualModeGcCarD(double habitualModeGcCarD) {
        this.habitualModeGcCarD = habitualModeGcCarD;
    }

    public double getHabitualModeGcCarP() {
        return habitualModeGcCarP;
    }

    public void setHabitualModeGcCarP(double habitualModeGcCarP) {
        this.habitualModeGcCarP = habitualModeGcCarP;
    }

    public double getHabitualModeGcPT() {
        return habitualModeGcPT;
    }

    public void setHabitualModeGcPT(double habitualModeGcPT) {
        this.habitualModeGcPT = habitualModeGcPT;
    }

    public double getHabitualModeGcBike() {
        return habitualModeBike;
    }

    public void setHabitualModeGcBike(double habitualModeBike) {
        this.habitualModeBike = habitualModeBike;
    }

    public double getHabitualModeGcWalk() {
        return habitualModeWalk;
    }

    public void setHabitualModeGcWalk(double habitualModeWalk) {
        this.habitualModeWalk = habitualModeWalk;
    }

}
