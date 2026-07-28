package abm.analysis;

import abm.data.DataSet;
import abm.data.geo.Zone;
import abm.data.plans.*;
import abm.data.pop.*;
import abm.io.input.DefaultDataReaderManager;
import abm.models.ModelSetup;
import abm.models.ModelSetupMuc;
import abm.models.modeChoice.NestedLogitTourModeChoiceModel;
import abm.properties.AbitResources;
import abm.scenarios.lowEmissionZones.io.LowEmissionZoneReader;
import abm.utils.AbitUtils;
import abm.utils.PlanTools;
import de.tum.bgu.msm.data.person.Disability;
import de.tum.bgu.msm.data.person.Gender;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.util.MitoUtil;
import org.apache.log4j.Logger;

import java.io.*;
import java.time.DayOfWeek;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class LogsumAnalysis {

    static Logger logger = Logger.getLogger(LogsumAnalysis.class);
    private static Map<String, Map<Purpose, Map<Integer, Map<Integer, Double>>>> logsumTableByPurpose_base;
    private static Map<String, Map<Purpose, Map<Integer, Map<Integer, Double>>>> logsumTableByPurpose_lowEmissionRestriction;
    private static final List<Person> personArrayList = new ArrayList<>();
    private static final  Map<String, Double> averageAgentAttributes_evOwner = new HashMap<>();
    private static final  Map<String, Double> averageAgentAttributes_nonEvOwner = new HashMap<>();
    private static Map<Integer, Boolean> evForbidden = new HashMap<>();
    private static DataSet dataSet;

    public static void main(String[] args) {

        AbitResources.initializeResources(args[0]);
        AbitUtils.loadHdf5Lib();

        MitoUtil.initializeRandomNumber(AbitUtils.getRandomObject());

        logger.info("Reading data");
        dataSet = new DefaultDataReaderManager().readData();

        logger.info("Creating the sub-models");
        ModelSetup modelSetup = new ModelSetupMuc(dataSet);
        NestedLogitTourModeChoiceModel modeChoiceModel = (NestedLogitTourModeChoiceModel) modelSetup.getTourModeChoice();

        logger.info("Initializing logsum calculator");
        generateSyntheticPopulation();
        evForbidden = new LowEmissionZoneReader(dataSet).readLowEmissionZones();

        for (Purpose purpose: Purpose.getAllPurposes()) {
            logger.info("Initializing logsum table for " + purpose + " purpose");
            initializeLogsumTable(purpose);

            logger.info("Calculating logsums for " + purpose + " purpose");
            personArrayList.stream().parallel().forEach(person -> calculateLogsums(person, modeChoiceModel, purpose));

            logger.info("Printing logsums for  " + purpose + " purpose");
            printLogsums(purpose);
        }
    }

    private static void calculateLogsums(Person person, NestedLogitTourModeChoiceModel modeChoiceModel, Purpose purpose) {

        for (Zone destinationZone : dataSet.getZones().values()){

            Plan plan = Plan.initializePlan(person);

            Activity homeAct = new Activity(person, Purpose.HOME);
            homeAct.setLocation(person.getHousehold().getLocation());

            Activity fakeActivity = new Activity(person, purpose);
            fakeActivity.setLocation(destinationZone);
            fakeActivity.setDayOfWeek(DayOfWeek.MONDAY);
            fakeActivity.setStartTime_min(480);
            fakeActivity.setEndTime_min(960);

            PlanTools planTools;
            planTools = new PlanTools(dataSet.getTravelTimes());
            planTools.addMainTour(plan, fakeActivity);

            Leg leg1 = new Leg(homeAct, fakeActivity);
            int travelTime1 = dataSet.getTravelTimes().getTravelTimeInMinutes(person.getHousehold().getLocation(), fakeActivity.getLocation(), Mode.UNKNOWN, fakeActivity.getStartTime_min());
            leg1.setTravelTime_min(travelTime1);

            Leg leg2 = new Leg(fakeActivity, homeAct);
            int travelTime2 = dataSet.getTravelTimes().getTravelTimeInMinutes(fakeActivity.getLocation(), person.getHousehold().getLocation(), Mode.UNKNOWN, fakeActivity.getEndTime_min());
            leg2.setTravelTime_min(travelTime2);

            Tour fakeTour = new Tour(fakeActivity, 1);
            fakeTour.getLegs().put(travelTime1, leg1);
            fakeTour.getLegs().put(travelTime2, leg2);
            fakeTour.getActivities().put(0, homeAct);
            fakeTour.getActivities().put(fakeActivity.getStartTime_min(), fakeActivity);
            fakeTour.getActivities().put(fakeActivity.getEndTime_min(), homeAct);
            fakeActivity.setTour(fakeTour);

            logsumTableByPurpose_base.get("evOwner").get(purpose).get(person.getHousehold().getLocation().getZoneId()).put(destinationZone.getId(), modeChoiceModel.calculateModeChoiceLogsumForThisODPairForBase(person, fakeTour, fakeActivity.getPurpose(), averageAgentAttributes_evOwner));
            //logsumTableByPurpose_base.get("nonEvOwner").get(purpose).get(person.getHousehold().getLocation().getZoneId()).put(destinationZone.getId(), modeChoiceModel.calculateModeChoiceLogsumForThisODPairForBase(person, fakeTour, fakeActivity.getPurpose(), averageAgentAttributes_nonEvOwner));

            boolean isLowEmissionZone = evForbidden.get(destinationZone.getId()) && !evForbidden.get(person.getHousehold().getLocation().getZoneId());
            //logsumTableByPurpose_lowEmissionRestriction.get("evOwner").get(purpose).get(person.getHousehold().getLocation().getZoneId()).put(destinationZone.getId(), modeChoiceModel.calculateModeChoiceLogsumForThisODPairForBase(person, fakeTour, fakeActivity.getPurpose(), averageAgentAttributes_evOwner));
            //logsumTableByPurpose_lowEmissionRestriction.get("nonEvOwner").get(purpose).get(person.getHousehold().getLocation().getZoneId()).put(destinationZone.getId(), modeChoiceModel.calculateModeChoiceLogsumForThisODPairForLowEmissionZoneRestriction(person, fakeTour, fakeActivity.getPurpose(), averageAgentAttributes_nonEvOwner, isLowEmissionZone));

        }
    }

    private static void printLogsums(Purpose purpose) {
        PrintWriter pw_base_evOwner;
        try {
            String role = "evOwner";
            pw_base_evOwner = new PrintWriter("D:/data/abm_temp/paper/logsums/logsumTable_"+ purpose + "_" + role + "_base.csv");
            pw_base_evOwner.println("origin,destination,logsum");
            for (Zone origin : dataSet.getZones().values()) {
                for (Zone destination : dataSet.getZones().values()) {
                    pw_base_evOwner.println(origin.getId() + "," + destination.getId() + "," + logsumTableByPurpose_base.get(role).get(purpose).get(origin.getId()).get(destination.getId()));
                }
            }
            pw_base_evOwner.close();
        } catch (FileNotFoundException e) {
            throw new RuntimeException(e);
        }

//        PrintWriter pw_base_nonEvOwner;
//        try {
//            String role = "nonEvOwner";
//            pw_base_nonEvOwner = new PrintWriter("D:/data/abm_temp/paper/logsums/logsumTable_"+ purpose + "_" + role + "_base.csv");
//            pw_base_nonEvOwner.println("origin,destination,logsum");
//            for (Zone origin : dataSet.getZones().values()) {
//                for (Zone destination : dataSet.getZones().values()) {
//                    pw_base_nonEvOwner.println(origin.getId() + "," + destination.getId() + "," + logsumTableByPurpose_base.get(role).get(purpose).get(origin.getId()).get(destination.getId()));
//                }
//            }
//            pw_base_nonEvOwner.close();
//        } catch (FileNotFoundException e) {
//            throw new RuntimeException(e);
//        }
        
//        PrintWriter pw_lowEmission_evOwner;
//        try {
//            String role = "evOwner";
//            pw_lowEmission_evOwner = new PrintWriter("D:/data/abm_temp/paper/logsums/logsumTable_"+ purpose + "_" + role + "_lowEmissionZoneRestriction_AltStadtRing.csv");
//            pw_lowEmission_evOwner.println("origin,destination,logsum");
//            for (Zone origin : dataSet.getZones().values()) {
//                for (Zone destination : dataSet.getZones().values()) {
//                    pw_lowEmission_evOwner.println(origin.getId() + "," + destination.getId() + "," + logsumTableByPurpose_lowEmissionRestriction.get(role).get(purpose).get(origin.getId()).get(destination.getId()));
//                }
//            }
//            pw_lowEmission_evOwner.close();
//            pw_lowEmission_evOwner.close();
//
//        } catch (FileNotFoundException e) {
//            throw new RuntimeException(e);
//        }

//        PrintWriter pw_lowEmission_nonEvOwner;
//        try {
//            String role = "nonEvOwner";
//            pw_lowEmission_nonEvOwner = new PrintWriter("D:/data/abm_temp/paper/logsums/logsumTable_"+ purpose + "_" + role + "_lowEmissionZoneRestriction_MittelerRing.csv");
//            pw_lowEmission_nonEvOwner.println("origin,destination,logsum");
//            for (Zone origin : dataSet.getZones().values()) {
//                for (Zone destination : dataSet.getZones().values()) {
//                    pw_lowEmission_nonEvOwner.println(origin.getId() + "," + destination.getId() + "," + logsumTableByPurpose_lowEmissionRestriction.get(role).get(purpose).get(origin.getId()).get(destination.getId()));
//                }
//            }
//            pw_lowEmission_nonEvOwner.close();
//            pw_lowEmission_nonEvOwner.close();
//
//        } catch (FileNotFoundException e) {
//            throw new RuntimeException(e);
//        }
    }

    private static void initializeLogsumTable(Purpose purpose) {
        logsumTableByPurpose_base = new ConcurrentHashMap<>();
        logsumTableByPurpose_lowEmissionRestriction = new ConcurrentHashMap<>();

        String[] roles = {"evOwner", "nonEvOwner"};

        for (String role : roles) {
            logsumTableByPurpose_base.putIfAbsent(role, new HashMap<>());
            logsumTableByPurpose_base.get(role).putIfAbsent(purpose, new HashMap<>());
            logsumTableByPurpose_lowEmissionRestriction.putIfAbsent(role, new HashMap<>());
            logsumTableByPurpose_lowEmissionRestriction.get(role).putIfAbsent(purpose, new HashMap<>());
            for (Zone origin : dataSet.getZones().values()) {
                logsumTableByPurpose_base.get(role).get(purpose).putIfAbsent(origin.getId(), new HashMap<>());
                logsumTableByPurpose_lowEmissionRestriction.get(role).get(purpose).putIfAbsent(origin.getId(), new HashMap<>());
                for (Zone destination : dataSet.getZones().values()) {
                    logsumTableByPurpose_base.get(role).get(purpose).get(origin.getId()).putIfAbsent(destination.getId(), 0.0);
                    logsumTableByPurpose_lowEmissionRestriction.get(role).get(purpose).get(origin.getId()).putIfAbsent(destination.getId(), 0.0);
                }
            }
        }
    }

    private static void generateSyntheticPopulation() {

        for (Zone originZone : dataSet.getZones().values()){
            Household averageHouseholdPerZone = new Household(originZone.getZoneId(), originZone, 0);
            averageHouseholdPerZone.setEconomicStatus(EconomicStatus.from0to800);
            Person averagePersonPerZone = new Person(originZone.getZoneId(), averageHouseholdPerZone, 32, Gender.MALE, Relationship.single,
                    Occupation.EMPLOYED, true, null, 0, 480, 480,
                    0, null, Disability.WITHOUT);
            averagePersonPerZone.setHabitualMode(HabitualMode.CAR_DRIVER);
            personArrayList.add(averagePersonPerZone);
        }

        averageAgentAttributes_evOwner.put("female", 0.5000);
        averageAgentAttributes_evOwner.put("age_0_18", 0.1659);
        averageAgentAttributes_evOwner.put("age_19_29", 0.1387);
        averageAgentAttributes_evOwner.put("age_30_49", 0.3083);
        averageAgentAttributes_evOwner.put("age_50_59", 0.1348);
        averageAgentAttributes_evOwner.put("age_60_69", 0.1145);
        averageAgentAttributes_evOwner.put("age_70", 0.1377);
        averageAgentAttributes_evOwner.put("mobilityRestricted", 0.0820);
        averageAgentAttributes_evOwner.put("averageHouseholdSize", 3.01);
        averageAgentAttributes_evOwner.put("hasChildren", 0.3410);
        averageAgentAttributes_evOwner.put("income_0_1500", 0.1680);
        averageAgentAttributes_evOwner.put("income_1501_5600", 0.7140);
        averageAgentAttributes_evOwner.put("income_5601", 0.1180);
        averageAgentAttributes_evOwner.put("numDaysWork", 0.0);
        averageAgentAttributes_evOwner.put("numDaysEducation", 0.0);
        averageAgentAttributes_evOwner.put("numDaysMandatory", 0.0);
        averageAgentAttributes_evOwner.put("habitualMode_carDriver", 0.0);
        averageAgentAttributes_evOwner.put("habitualMode_carPassenger", 0.0);
        averageAgentAttributes_evOwner.put("habitualMode_pt", 0.0);
        averageAgentAttributes_evOwner.put("habitualMode_bike", 0.0);
        averageAgentAttributes_evOwner.put("habitualMode_walk", 0.0);

        averageAgentAttributes_nonEvOwner.put("female", 0.5110);
        averageAgentAttributes_nonEvOwner.put("age_0_18", 0.1803);
        averageAgentAttributes_nonEvOwner.put("age_19_29", 0.1370);
        averageAgentAttributes_nonEvOwner.put("age_30_49", 0.3151);
        averageAgentAttributes_nonEvOwner.put("age_50_59", 0.1441);
        averageAgentAttributes_nonEvOwner.put("age_60_69", 0.1061);
        averageAgentAttributes_nonEvOwner.put("age_70", 0.1175);
        averageAgentAttributes_nonEvOwner.put("mobilityRestricted", 0.0870);
        averageAgentAttributes_nonEvOwner.put("averageHouseholdSize", 2.75);
        averageAgentAttributes_nonEvOwner.put("hasChildren", 0.3150);
        averageAgentAttributes_nonEvOwner.put("income_0_1500", 0.2410);
        averageAgentAttributes_nonEvOwner.put("income_1501_5600", 0.6770);
        averageAgentAttributes_nonEvOwner.put("income_5601", 0.08170);
        averageAgentAttributes_nonEvOwner.put("numDaysWork", 0.0);
        averageAgentAttributes_nonEvOwner.put("numDaysEducation", 0.0);
        averageAgentAttributes_nonEvOwner.put("numDaysMandatory", 0.0);
        averageAgentAttributes_nonEvOwner.put("habitualMode_carDriver", 0.0);
        averageAgentAttributes_nonEvOwner.put("habitualMode_carPassenger", 0.0);
        averageAgentAttributes_nonEvOwner.put("habitualMode_pt", 0.0);
        averageAgentAttributes_nonEvOwner.put("habitualMode_bike", 0.0);
        averageAgentAttributes_nonEvOwner.put("habitualMode_walk", 0.0);


    }


}
