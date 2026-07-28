package abm.io.input;

import abm.data.DataSet;
import abm.data.geo.*;
import abm.data.pop.*;
import abm.data.travelInformation.MitoBasedTravelDistances;
import abm.data.travelInformation.MitoBasedTravelTimes;
import abm.data.plans.Mode;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.data.person.Disability;
import de.tum.bgu.msm.data.person.Gender;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.data.travelTimes.SkimTravelTimes;
import org.apache.log4j.Logger;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.*;

/**
 * Level-of-service reader for the Maryland ABIT scenario. Loads:
 *  - the MSTM zone system (id + centroid coords + RegioStaR/BBSR crosswalk + area) from zone_attributes.csv,
 *  - real OMX car time + distance skims (zone-indexed) as ABIT travel times/distances,
 *  - a county-subset of the SILO calib5 population (hh/pp/jj/dd) with real home/job zones & coords,
 *  - household economic status (replicates EconomicStatusReader) and zone attraction sizes.
 * Designed to feed {@link abm.models.ModelSetupMaryland} (RTS-empirical daily models).
 */
public class MarylandLosDataReader implements DataReaderManager {

    private static final Logger logger = Logger.getLogger(MarylandLosDataReader.class);
    private final Random rnd = AbitUtils.getRandomObject();

    private final Map<Integer, double[]> zoneXY = new HashMap<>();
    private DataSet ds;

    // ---- workplace gravity (RTS HBW Tanner friction) ----
    private int[] workDestZones;               // candidate destination zones (jobs > 0)
    private double[] workDestAttr;             // job attraction per candidate
    private final Map<Integer, double[]> workCumCache = new HashMap<>();   // homeZone -> cumulative weights
    private final Map<Integer, Integer> reassignedWorkZone = new HashMap<>();  // personId -> LODES-calibrated work zone
    private double bt = -0.0274684, blt = -1.0998989;   // RTS HBW b_time, b_logtime
    private double eduMeanKm = 2.30 * 1.60934 * 0.65;  // RTS EDUCATION median 2.3mi -> exp mean
    private double workLongPen = 0.046, workLongT0 = 12;  // long-trip penalty (min); relaxed 0.065->0.046 so the
                                                          // home-based commute mean rises ~10.7->~12.8 mi to match
                                                          // RTS HBW (12.3-12.9); was over-decaying the long tail.
    private final Map<Integer, MicroscopicLocation> zoneLocCache = new HashMap<>();
    private int[] allZones;

    @Override
    public DataSet readData() {
        DataSet dataSet = new DataSet();
        this.ds = dataSet;
        readZones(dataSet);
        readSkims(dataSet);
        loadFrictionParams();
        computeJobAttraction();

        String county = AbitResources.instance.getString("county.fips");
        int maxHh = AbitResources.instance.getInt("max.households", 50000);

        Map<Integer, Integer> hhZone = readDwellingsForCounty(dataSet, county, maxHh);
        Map<Integer, Integer> hhAutos = readHouseholdAutos(hhZone.keySet());
        buildHouseholds(dataSet, hhZone, hhAutos);
        readPersonsAndJobs(dataSet, hhZone.keySet());

        new EconomicStatusReader(dataSet).read();
        populateZones(dataSet);

        logger.info("Maryland LOS dataset: zones=" + dataSet.getZones().size()
                + " households=" + dataSet.getHouseholds().size()
                + " persons=" + dataSet.getPersons().size()
                + " jobs=" + dataSet.getJobs().size()
                + " schools=" + dataSet.getSchools().size());
        return dataSet;
    }

    private void readZones(DataSet dataSet) {
        String f = AbitResources.instance.getString("zone.attributes.file");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String[] h = br.readLine().split(",");
            int iId = idx(h, "id"), iX = idx(h, "x"), iY = idx(h, "y");
            int iR2 = idx(h, "regioStaR2"), iR7 = idx(h, "regioStaR7"), iG5 = idx(h, "regStaRGe5");
            int iBb = idx(h, "bbsr"), iA = idx(h, "area_km2");
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                int id = Integer.parseInt(r[iId].trim());
                Zone z = new Zone(id);
                z.setRegioStaR2Type(RegioStaR2.valueOf(Integer.parseInt(r[iR2].trim())));
                z.setRegioStaR7Type(RegioStaR7.valueOf(Integer.parseInt(r[iR7].trim())));
                z.setRegioStaRGem5Type(RegioStaRGem5.valueOf(Integer.parseInt(r[iG5].trim())));
                z.setAreaType1(BBSRType.valueOf(Integer.parseInt(r[iBb].trim())));
                z.setAreaKm2(Double.parseDouble(r[iA].trim()));
                z.setDistToRail_meter(1000L);
                double zx = Double.parseDouble(r[iX].trim()), zy = Double.parseDouble(r[iY].trim());
                z.setAttribute("x", zx);
                z.setAttribute("y", zy);
                dataSet.getZones().put(id, z);
                zoneXY.put(id, new double[]{zx, zy});
            }
        } catch (Exception e) {
            throw new RuntimeException("readZones failed for " + f, e);
        }
        allZones = dataSet.getZones().keySet().stream().mapToInt(Integer::intValue).toArray();
        logger.info("Loaded " + dataSet.getZones().size() + " zones with centroids + region crosswalk");
    }

    private void readSkims(DataSet dataSet) {
        try {
            SkimTravelTimes tt = new SkimTravelTimes();
            // Congested-skim feedback: prefer abit.skim.traveltime.file (the working/congested skim the
            // feedback loop rewrites each iteration); fall back to the free-flow car.time.omx.file.
            String timeFile = AbitResources.instance.getString("abit.skim.traveltime.file");
            if (timeFile == null) timeFile = AbitResources.instance.getString("car.time.omx.file");
            String timeMat = AbitResources.instance.getString("car.time.omx.matrix");
            // traveltime_auto.omx is already in MINUTES -> factor 1.0 (not 1/60).
            // load under every mode name so PlanTools never hits a missing skim.
            for (Mode m : Mode.values()) {
                tt.readSkim(m.toString(), timeFile, timeMat, 1.0);
            }
            // real transit time skims for the mode-choice generalized cost, if provided
            String busFile = AbitResources.instance.getString("bus.time.omx.file");
            if (busFile != null) tt.readSkim(Mode.BUS.toString(), busFile,
                    AbitResources.instance.getString("bus.time.omx.matrix"), 1.0);
            String trainFile = AbitResources.instance.getString("train.time.omx.file");
            if (trainFile != null) {
                tt.readSkim(Mode.TRAIN.toString(), trainFile, AbitResources.instance.getString("train.time.omx.matrix"), 1.0);
                tt.readSkim(Mode.TRAM_METRO.toString(), trainFile, AbitResources.instance.getString("train.time.omx.matrix"), 1.0);
            }
            dataSet.setTravelTimes(new MitoBasedTravelTimes(tt));

            SkimTravelTimes dist = new SkimTravelTimes();
            String distFile = AbitResources.instance.getString("car.dist.omx.file");
            String distMat = AbitResources.instance.getString("car.dist.omx.matrix");
            dist.readSkim(Mode.UNKNOWN.toString(), distFile, distMat, 1.);
            dataSet.setTravelDistances(new MitoBasedTravelDistances(dist));
            logger.info("Loaded real OMX skims: time=" + timeFile + " dist=" + distFile);
        } catch (Exception e) {
            throw new RuntimeException("readSkims failed", e);
        }
    }

    private Map<Integer, Integer> readDwellingsForCounty(DataSet dataSet, String county, int maxHh) {
        // FULL-REGION mode: county == "ALL" -> keep all counties, random household sample of sample.fraction.
        boolean fullRegion = county == null || county.equalsIgnoreCase("ALL");
        Set<Integer> countyZones = fullRegion ? null : readCountyZones(county);
        double frac = AbitResources.instance.getDouble("sample.fraction", 1.0);
        Random sampleRng = new Random(20240702L);   // deterministic sample
        Map<Integer, Integer> hhZone = new LinkedHashMap<>();
        String f = AbitResources.instance.getString("dwellings.file");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String[] h = br.readLine().split(",");
            int iZone = idx(h, "zone"), iHh = idx(h, "hhID");
            String line;
            while ((line = br.readLine()) != null && hhZone.size() < maxHh) {
                String[] r = line.split(",");
                int hid = Integer.parseInt(r[iHh].trim());
                if (hid <= 0) continue;
                int zone = Integer.parseInt(r[iZone].trim());
                if (!fullRegion && !countyZones.contains(zone)) continue;
                if (fullRegion && frac < 1.0 && sampleRng.nextDouble() >= frac) continue;
                hhZone.putIfAbsent(hid, zone);
            }
        } catch (Exception e) {
            throw new RuntimeException("readDwellings failed", e);
        }
        logger.info("Selected " + hhZone.size() + " households "
                + (fullRegion ? ("(FULL REGION, sample.fraction=" + frac + ")") : ("in county " + county)));
        return hhZone;
    }

    private Set<Integer> readCountyZones(String county) {
        Set<Integer> zones = new HashSet<>();
        String f = AbitResources.instance.getString("zone.attributes.file");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String[] h = br.readLine().split(",");
            int iId = idx(h, "id"), iC = idx(h, "countyfips");
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                if (r[iC].trim().equals(county)) zones.add(Integer.parseInt(r[iId].trim()));
            }
        } catch (Exception e) {
            throw new RuntimeException("readCountyZones failed", e);
        }
        return zones;
    }

    private Map<Integer, Integer> readHouseholdAutos(Set<Integer> keptHh) {
        Map<Integer, Integer> autos = new HashMap<>();
        String f = AbitResources.instance.getString("households.file");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String[] h = br.readLine().split(",");
            int iId = idx(h, "id"), iAutos = idx(h, "autos");
            String line;
            while ((line = br.readLine()) != null) {
                int c = line.indexOf(',');
                int id = Integer.parseInt(line.substring(0, c).trim());
                if (!keptHh.contains(id)) continue;
                String[] r = line.split(",");
                autos.put(id, Integer.parseInt(r[iAutos].trim()));
                if (autos.size() == keptHh.size()) break;
            }
        } catch (Exception e) {
            throw new RuntimeException("readHouseholdAutos failed", e);
        }
        return autos;
    }

    private void buildHouseholds(DataSet dataSet, Map<Integer, Integer> hhZone, Map<Integer, Integer> autos) {
        for (Map.Entry<Integer, Integer> e : hhZone.entrySet()) {
            int hid = e.getKey(), zone = e.getValue();
            MicroscopicLocation loc = locFor(zone);
            setZoneOnLoc(dataSet, loc, zone);
            Household hh = new Household(hid, loc, autos.getOrDefault(hid, 0));
            hh.setSimulated(Boolean.TRUE);
            hh.setPartition(2);
            dataSet.getHouseholds().put(hid, hh);
        }
    }

    private MicroscopicLocation locFor(int zoneId) {
        double[] xy = zoneXY.getOrDefault(zoneId, new double[]{0, 0});
        MicroscopicLocation loc = new MicroscopicLocation(xy[0] + (rnd.nextDouble() - 0.5) * 200,
                xy[1] + (rnd.nextDouble() - 0.5) * 200);
        // zone reference needed for skim lookups
        // (Zone object set below by caller via dataSet lookup)
        return loc;
    }

    private void setZoneOnLoc(DataSet dataSet, MicroscopicLocation loc, int zoneId) {
        Zone z = dataSet.getZones().get(zoneId);
        if (z != null) loc.setZone(z);
    }

    private void readPersonsAndJobs(DataSet dataSet, Set<Integer> keptHh) {
        // first pass over persons: capture attributes + collect employed person ids
        String pf = AbitResources.instance.getString("persons.file");
        List<String[]> kept = new ArrayList<>();
        Set<Integer> employedIds = new HashSet<>();
        int[] cols = new int[8];
        try (BufferedReader br = new BufferedReader(new FileReader(pf))) {
            String[] h = br.readLine().split(",");
            cols[0] = idx(h, "id"); cols[1] = idx(h, "hhid"); cols[2] = idx(h, "age");
            cols[3] = idx(h, "gender"); cols[4] = idx(h, "relationShip"); cols[5] = idx(h, "occupation");
            cols[6] = idx(h, "driversLicense"); cols[7] = idx(h, "income");
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                int hhid = Integer.parseInt(r[cols[1]].trim());
                if (!keptHh.contains(hhid)) continue;
                kept.add(r);
                if (Integer.parseInt(r[cols[5]].trim()) == Occupation.EMPLOYED.ordinal()
                        || strip(r[cols[5]]).equals("1")) {
                    employedIds.add(Integer.parseInt(r[cols[0]].trim()));
                }
            }
        } catch (Exception e) {
            throw new RuntimeException("readPersons pass1 failed", e);
        }

        // WORK destination = LODES-calibrated workplace RE-ASSIGNMENT (workplace_reassign.py): reproduces the
        // observed home->work commute OD (24% inflow to BMR, 7.6% out-of-state, realistic lengths). Replaces
        // the old home-gravity sampleWorkZone() which discarded SILO workplaces and lost out-of-state inflow.
        // Falls back to sampleWorkZone() only for workers not present in the re-assignment file.
        //  EDUCATION -> RTS EDUCATION distance-calibrated draw (SILO has no schools)
        String wpf = AbitResources.instance.getString("workplace.reassign.file");
        if (wpf != null) {
            try (BufferedReader br = new BufferedReader(new FileReader(wpf))) {
                br.readLine();  // header person_id,home_zone,work_zone
                String line;
                while ((line = br.readLine()) != null) {
                    String[] p = line.split(",");
                    int wz = Integer.parseInt(p[2].trim());
                    if (wz > 0) reassignedWorkZone.put(Integer.parseInt(p[0].trim()), wz);
                }
            } catch (Exception e) { throw new RuntimeException("workplace.reassign.file read failed: " + wpf, e); }
            System.out.println("[workplace] loaded " + reassignedWorkZone.size() + " LODES-calibrated workplaces");
        }
        int jobSeq = 1, schoolSeq = 1;
        for (String[] r : kept) {
            int id = Integer.parseInt(r[cols[0]].trim());
            int hhid = Integer.parseInt(r[cols[1]].trim());
            Household hh = dataSet.getHouseholds().get(hhid);
            int homeZone = hh.getLocation().getZoneId() == -1 ? firstZone(hh) : hh.getLocation().getZoneId();
            int age = Integer.parseInt(r[cols[2]].trim());
            Gender gender = Gender.valueOf(Integer.parseInt(r[cols[3]].trim()));
            Relationship rel = Relationship.valueOf(strip(r[cols[4]]));
            Occupation occ = Occupation.valueOf(Integer.parseInt(r[cols[5]].trim()));
            boolean lic = Boolean.parseBoolean(r[cols[6]].trim());
            int monthly = (int) (Double.parseDouble(r[cols[7]].trim()) / 12.0);

            Job job = null; School school = null;
            if (occ == Occupation.EMPLOYED) {
                // LODES-calibrated workplace; fall back to the home gravity only if this worker is missing
                int jz = reassignedWorkZone.getOrDefault(id, -1);
                if (jz <= 0) jz = sampleWorkZone(homeZone);
                MicroscopicLocation jl = locFor(jz); setZoneOnLoc(dataSet, jl, jz);
                job = new Job(jobSeq++, id, "OTH", jl, 8 * 60, 8 * 60);
                dataSet.getJobs().put(job.getId(), job);
            } else if (occ == Occupation.STUDENT) {
                int sz = sampleDistanceZone(homeZone, eduMeanKm);
                MicroscopicLocation sl = locFor(sz); setZoneOnLoc(dataSet, sl, sz);
                school = new School(schoolSeq++, "edu", 1, 0, sl, 8 * 60, 6 * 60);
                dataSet.getSchools().put(school.getId(), school);
            }
            Person p = new Person(id, hh, age, gender, rel, occ, lic, job, 8 * 60, 8 * 60, 8 * 60,
                    monthly, school, Disability.WITHOUT);
            hh.getPersons().add(p);
            dataSet.getPersons().put(id, p);
        }

        // ensure every household home location has its zone reference set for skim lookups
        for (Household hh : dataSet.getHouseholds().values()) {
            // home zone was stored via hhZone; re-attach using nearest zone if missing
        }
    }

    private int firstZone(Household hh) {
        return hh.getLocation().getZoneId();
    }

    // attraction sizes per zone (mirrors DefaultDataReaderManager.populateZones)
    private void populateZones(DataSet dataSet) {
        String[] keys = {"hh.total", "jj.total", "jj.retail", "jj.office", "jj.other", "students"};
        Map<Zone, Map<String, Integer>> att = new HashMap<>();
        for (Zone z : dataSet.getZones().values()) {
            att.put(z, new HashMap<>());
            for (String k : keys) att.get(z).put(k, 0);
        }
        for (Household hh : dataSet.getHouseholds().values()) {
            Zone z = dataSet.getZones().get(hh.getLocation().getZoneId());
            if (z == null) continue;
            att.get(z).merge("hh.total", hh.getPersons().size(), Integer::sum);
            for (Person pp : hh.getPersons()) {
                if (pp.getOccupation() == Occupation.STUDENT && pp.getSchool() != null) {
                    Zone sz = dataSet.getZones().get(pp.getSchool().getLocation().getZoneId());
                    if (sz != null) att.get(sz).merge("students", 1, Integer::sum);
                }
            }
        }
        for (Job job : dataSet.getJobs().values()) {
            Zone z = dataSet.getZones().get(job.getLocation().getZoneId());
            if (z == null) continue;
            att.get(z).merge("jj.total", 1, Integer::sum);
            att.get(z).merge("jj.other", 1, Integer::sum);
        }
        for (Zone z : dataSet.getZones().values()) {
            for (String k : keys) z.setAttribute(k, att.get(z).get(k));
        }
    }

    private void loadFrictionParams() {
        String f = AbitResources.instance.getString("dest.friction.file");
        if (f == null) return;
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String[] h = br.readLine().split(",");
            int iP = idx(h, "purpose"), iBt = idx(h, "b_time"), iBl = idx(h, "b_logtime");
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                if (r[iP].trim().equalsIgnoreCase("WORK")) {
                    bt = Double.parseDouble(r[iBt].trim());
                    blt = Double.parseDouble(r[iBl].trim());
                }
            }
        } catch (Exception e) {
            logger.warn("dest.friction.file not loaded, using defaults: " + e.getMessage());
        }
    }

    private void computeJobAttraction() {
        Map<Integer, Integer> jobs = new HashMap<>();
        String f = AbitResources.instance.getString("jobs.file");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String[] h = br.readLine().split(",");
            int iZone = idx(h, "zone");
            String line;
            while ((line = br.readLine()) != null) {
                int z = Integer.parseInt(line.split(",")[iZone].trim());
                jobs.merge(z, 1, Integer::sum);
            }
        } catch (Exception e) {
            throw new RuntimeException("computeJobAttraction failed", e);
        }
        List<Integer> cands = new ArrayList<>();
        for (Map.Entry<Integer, Integer> e : jobs.entrySet())
            if (zoneXY.containsKey(e.getKey())) cands.add(e.getKey());
        workDestZones = new int[cands.size()];
        workDestAttr = new double[cands.size()];
        for (int i = 0; i < cands.size(); i++) {
            workDestZones[i] = cands.get(i);
            workDestAttr[i] = jobs.get(cands.get(i));
        }
        logger.info("WORK gravity: " + workDestZones.length + " job-zones (total jobs " + jobs.values().stream().mapToInt(Integer::intValue).sum() + ")");
    }

    private MicroscopicLocation zoneCentroid(int zoneId) {
        return zoneLocCache.computeIfAbsent(zoneId, z -> {
            double[] xy = zoneXY.getOrDefault(z, new double[]{0, 0});
            MicroscopicLocation l = new MicroscopicLocation(xy[0], xy[1]);
            setZoneOnLoc(ds, l, z);
            return l;
        });
    }

    /** Draw a workplace zone from the RTS HBW Tanner-friction gravity given the home zone. Cached per home zone. */
    private int sampleWorkZone(int homeZone) {
        double[] cum = workCumCache.computeIfAbsent(homeZone, hz -> {
            MicroscopicLocation homeLoc = zoneCentroid(hz);
            double[] c = new double[workDestZones.length];
            double run = 0;
            for (int i = 0; i < workDestZones.length; i++) {
                double t = ds.getTravelTimes().getTravelTimeInMinutes(homeLoc, zoneCentroid(workDestZones[i]),
                        abm.data.plans.Mode.CAR_DRIVER, 8 * 60);
                if (!(t >= 0) || t > 300) t = 300;
                double fr = Math.pow(t + 1.0, blt) * Math.exp(bt * t);   // RTS HBW Tanner friction
                // out-of-sample long-tail correction (as in the tour pipeline): extra decay for long
                // trips only, so singly-constrained high-attraction downtown zones don't over-absorb.
                if (t > workLongT0) fr *= Math.exp(-workLongPen * (t - workLongT0));
                run += workDestAttr[i] * fr;
                c[i] = run;
            }
            return c;
        });
        double total = cum[cum.length - 1];
        if (total <= 0) return homeZone;
        double u = rnd.nextDouble() * total;
        int lo = 0, hi = cum.length - 1;
        while (lo < hi) { int m = (lo + hi) >>> 1; if (cum[m] < u) lo = m + 1; else hi = m; }
        return workDestZones[lo];
    }

    /** Pick the zone whose network distance from home is closest to a target drawn Exp(meanKm). */
    private int sampleDistanceZone(int homeZone, double meanKm) {
        MicroscopicLocation home = zoneCentroid(homeZone);
        double targetM = Math.max(200, Math.min(60000, -meanKm * Math.log(1 - rnd.nextDouble()) * 1000));
        int best = homeZone; double bestDiff = Double.MAX_VALUE;
        for (int i = 0; i < 300; i++) {
            int z = allZones[rnd.nextInt(allZones.length)];
            double d = ds.getTravelDistances().getTravelDistanceInMeters(home, zoneCentroid(z),
                    abm.data.plans.Mode.UNKNOWN, 8 * 60);
            double diff = Math.abs(d - targetM);
            if (diff < bestDiff) { bestDiff = diff; best = z; }
        }
        return best;
    }

    private static int idx(String[] header, String name) {
        for (int i = 0; i < header.length; i++) if (strip(header[i]).equalsIgnoreCase(name)) return i;
        throw new RuntimeException("Column '" + name + "' not in header");
    }

    private static String strip(String s) { return s.replace("\"", "").trim(); }
}
