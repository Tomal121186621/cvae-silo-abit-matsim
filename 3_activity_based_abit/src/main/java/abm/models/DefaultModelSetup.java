package abm.models;

import abm.data.DataSet;
import abm.data.plans.Activity;
import abm.data.plans.Purpose;
import abm.models.activityGeneration.frequency.FrequencyGenerator;
import abm.models.activityGeneration.frequency.FrequencyGeneratorModel;
import abm.models.activityGeneration.frequency.SimpleSubtourGenerator;
import abm.models.activityGeneration.frequency.SubtourGenerator;
import abm.models.activityGeneration.splitByType.*;
import abm.models.activityGeneration.time.*;
import abm.models.destinationChoice.DestinationChoice;
import abm.models.destinationChoice.DestinationChoiceModel;
import abm.models.destinationChoice.SubtourDestinationChoice;
import abm.models.destinationChoice.SubtourDestinationChoiceModel;
import abm.models.modeChoice.*;
import abm.utils.AbitUtils;
import org.apache.commons.collections.map.HashedMap;

import java.util.Map;
import java.util.Random;

public class DefaultModelSetup implements ModelSetup{

    private final Map<Purpose, FrequencyGenerator> frequencyGenerators;
    private final HabitualModeChoice habitualModeChoice;
    private final DestinationChoice destinationChoice;
    private final TourModeChoice tourModeChoice;
    private final DayOfWeekMandatoryAssignment dayOfWeekMandatoryAssignment;
    private final DayOfWeekDiscretionaryAssignment dayOfWeekDiscretionaryAssignment;
    private final TimeAssignment timeAssignment;
    private final SplitByType splitByType;
    private final SplitStopType stopSplitType;
    private final SubtourGenerator subtourGenerator;
    private final SubtourTimeAssignment subtourTimeAssignment;
    private final SubtourDestinationChoice subtourDestinationChoice;
    private final SubtourModeChoice subtourModeChoice;


    public DefaultModelSetup(DataSet dataSet) {


        dayOfWeekMandatoryAssignment = new SimpleDayOfWeekMandatoryAssignment();
        tourModeChoice = new SimpleTourModeChoice(dataSet);
        habitualModeChoice = new SimpleHabitualModeChoice();
        dayOfWeekDiscretionaryAssignment = new SimpleDayOfWeekDiscretionaryAssignment();

        frequencyGenerators = new HashedMap();
        for (Purpose purpose : Purpose.getAllPurposes()){
            frequencyGenerators.put(purpose, new FrequencyGeneratorModel(dataSet, purpose));
        }
        stopSplitType = new SplitStopByTypeModel();
        splitByType = new SplitByTypeModel(dataSet);
        destinationChoice = new DestinationChoiceModel(dataSet);
        timeAssignment = new TimeAssignmentModel(dataSet);

        subtourGenerator = new SimpleSubtourGenerator();
        subtourTimeAssignment = new SimpleSubtourTimeAssignment();
        subtourDestinationChoice  =new SubtourDestinationChoiceModel(dataSet);
        subtourModeChoice = new SimpleSubtourModeChoice();




    }

    @Override
    public HabitualModeChoice getHabitualModeChoice() {
        return habitualModeChoice;
    }

    @Override
    public Map<Purpose, FrequencyGenerator> getFrequencyGenerator() {
        return frequencyGenerators;
    }

    @Override
    public DestinationChoice getDestinationChoice() {
        return destinationChoice;
    }

    @Override
    public TourModeChoice getTourModeChoice() {
        return tourModeChoice;
    }

    @Override
    public DayOfWeekMandatoryAssignment getDayOfWeekMandatoryAssignment() {
        return dayOfWeekMandatoryAssignment;
    }

    @Override
    public DayOfWeekDiscretionaryAssignment getDayOfWeekDiscretionaryAssignment() {
        return dayOfWeekDiscretionaryAssignment;
    }

    @Override
    public TimeAssignment getTimeAssignment() {
        return timeAssignment;
    }

    @Override
    public SplitByType getSplitByType() {
        return splitByType;
    }

    @Override
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
