package abm.models;

import abm.data.DataSet;
import abm.data.plans.Purpose;
import abm.io.input.BikeOwnershipReader;
import abm.models.activityGeneration.frequency.*;
import abm.models.activityGeneration.splitByType.SplitByType;
import abm.models.activityGeneration.splitByType.SplitByTypeModel;
import abm.models.activityGeneration.splitByType.SplitStopByTypeModel;
import abm.models.activityGeneration.splitByType.SplitStopType;
import abm.models.activityGeneration.time.*;
import abm.models.destinationChoice.DestinationChoice;
import abm.models.destinationChoice.DestinationChoiceModel;
import abm.models.destinationChoice.SubtourDestinationChoice;
import abm.models.destinationChoice.SubtourDestinationChoiceModel;
import abm.models.modeChoice.*;
import org.apache.commons.collections.map.HashedMap;

import java.util.Map;

public class ModelSetupMuc implements ModelSetup{

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
    private final BikeOwnershipReader bikeOwnershipReader;


    public ModelSetupMuc(DataSet dataSet) {

        bikeOwnershipReader = new BikeOwnershipReader(dataSet);
        dayOfWeekMandatoryAssignment = new DayOfWeekMandatoryAssignmentModel(dataSet);
        tourModeChoice = new NestedLogitTourModeChoiceModel(dataSet);
        habitualModeChoice = new NestedLogitHabitualModeChoiceModel(dataSet);
        dayOfWeekDiscretionaryAssignment = new DayOfWeekDiscretionaryAssignmentModel(dataSet);

        frequencyGenerators = new HashedMap();
        for (Purpose purpose : Purpose.getAllPurposes()){
            frequencyGenerators.put(purpose, new FrequencyGeneratorModel(dataSet, purpose));
        }
        stopSplitType = new SplitStopByTypeModel();
        splitByType = new SplitByTypeModel(dataSet);
        destinationChoice = new DestinationChoiceModel(dataSet);
        timeAssignment = new TimeAssignmentModel(dataSet);

        subtourGenerator = new SubtourGeneratorModel(dataSet);
        subtourTimeAssignment = new SubtourTimeAssignmentModel(dataSet);
        subtourDestinationChoice  =new SubtourDestinationChoiceModel(dataSet);
        subtourModeChoice = new SubtourModeChoiceModel(dataSet);

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
    public BikeOwnershipReader getBikeOwnershipReader() {
        return bikeOwnershipReader;
    }

}
