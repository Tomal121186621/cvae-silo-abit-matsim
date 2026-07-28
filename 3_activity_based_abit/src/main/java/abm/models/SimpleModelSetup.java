package abm.models;

import abm.data.DataSet;
import abm.data.plans.Purpose;
import abm.models.activityGeneration.frequency.FrequencyGenerator;
import abm.models.activityGeneration.frequency.SimpleFrequencyGenerator;
import abm.models.activityGeneration.frequency.SimpleSubtourGenerator;
import abm.models.activityGeneration.frequency.SubtourGenerator;
import abm.models.activityGeneration.splitByType.SimpleSplitByType;
import abm.models.activityGeneration.splitByType.SimpleSplitStopTypeModelWithAvailability;
import abm.models.activityGeneration.splitByType.SplitByType;
import abm.models.activityGeneration.splitByType.SplitStopType;
import abm.models.activityGeneration.time.*;
import abm.models.destinationChoice.DestinationChoice;
import abm.models.destinationChoice.SimpleDestinationChoice;
import abm.models.destinationChoice.SimpleSubtourDestination;
import abm.models.destinationChoice.SubtourDestinationChoice;
import abm.models.modeChoice.*;
import org.apache.commons.collections.map.HashedMap;

import java.util.Map;

public class SimpleModelSetup implements ModelSetup {


    private static Map<Purpose, FrequencyGenerator> frequencyGenerators;
    private static HabitualModeChoice habitualModeChoice;
    private static DestinationChoice destinationChoice;
    private static TourModeChoice tourModeChoice;
    private static DayOfWeekMandatoryAssignment dayOfWeekMandatoryAssignment;
    private static DayOfWeekDiscretionaryAssignment dayOfWeekDiscretionaryAssignment = new SimpleDayOfWeekDiscretionaryAssignment();
    private static TimeAssignment timeAssignment;
    private static SplitByType splitByType;
    private static SplitStopType stopSplitType;
    private final SubtourGenerator subtourGenerator;
    private final SubtourTimeAssignment subtourTimeAssignment;
    private final SubtourDestinationChoice subtourDestinationChoice;
    private SubtourModeChoice subtourModeChoice;

    public SimpleModelSetup(DataSet dataSet) {

        stopSplitType = new SimpleSplitStopTypeModelWithAvailability();
        splitByType = new SimpleSplitByType();
        timeAssignment = new SimpleTimeAssignmentWithTimeAvailability();
        dayOfWeekMandatoryAssignment = new SimpleDayOfWeekMandatoryAssignment();
        destinationChoice = new SimpleDestinationChoice();
        tourModeChoice = new SimpleTourModeChoice(dataSet);
        habitualModeChoice = new SimpleHabitualModeChoice();
        frequencyGenerators = new HashedMap();
        for (Purpose purpose : Purpose.getAllPurposes()){
            frequencyGenerators.put(purpose, new SimpleFrequencyGenerator());
        }
        subtourGenerator = new SimpleSubtourGenerator();
        subtourTimeAssignment = new SimpleSubtourTimeAssignment();
        subtourDestinationChoice = new SimpleSubtourDestination();
        subtourModeChoice = new SimpleSubtourModeChoice();

    }

    public HabitualModeChoice getHabitualModeChoice() {
        return habitualModeChoice;
    }

    public Map<Purpose, FrequencyGenerator> getFrequencyGenerator() {
        return frequencyGenerators;
    }

    public DestinationChoice getDestinationChoice() {
        return destinationChoice;
    }

    public TourModeChoice getTourModeChoice() {
        return tourModeChoice;
    }

    public DayOfWeekMandatoryAssignment getDayOfWeekMandatoryAssignment() {
        return dayOfWeekMandatoryAssignment;
    }

    public DayOfWeekDiscretionaryAssignment getDayOfWeekDiscretionaryAssignment() {
        return dayOfWeekDiscretionaryAssignment;
    }

    public TimeAssignment getTimeAssignment() {
        return timeAssignment;
    }

    public SplitByType getSplitByType() {
        return splitByType;
    }

    public SplitStopType getStopSplitType() {
        return stopSplitType;
    }

    @Override
    public SubtourGenerator getSubtourGenerator() {
        return subtourGenerator;
    }

    @Override
    public SubtourTimeAssignment getSubtourTimeAssignment() {
        return subtourTimeAssignment;
    }

    @Override
    public SubtourDestinationChoice getSubtourDestinationChoice() {
        return subtourDestinationChoice;
    }

    @Override
    public SubtourModeChoice getSubtourModeChoice() {
        return subtourModeChoice;
    }
}
