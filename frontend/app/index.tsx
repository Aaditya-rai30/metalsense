import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  Modal,
  Dimensions,
  useWindowDimensions,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import * as DocumentPicker from "expo-document-picker";
import * as XLSX from "xlsx";
import { Ionicons } from "@expo/vector-icons";
import Svg, { Circle, Line, Path, Text as SvgText } from "react-native-svg";
import Constants from "expo-constants";
import AsyncStorage from "@react-native-async-storage/async-storage";

/* ============================================================
 * T HEME       *
 * ============================================================ */

const LIGHT_C = {
  bg: "#EEFDF8",
  surface: "#FFFFFF",
  sidebar: "#FBFDFC",
  green: "#249E73",
  greenDark: "#188E68",
  teal: "#0C92A3",
  cyan: "#73D3DA",
  mint: "#DDF7F1",
  mint2: "#E8FAF6",
  border: "#D4ECE5",
  text: "#405168",
  muted: "#9AA8AA",
  muted2: "#B1BDBE",
  danger: "#C94D4D",
  warning: "#D6A329",
  high: "#DE7A32",
  white: "#FFFFFF",
};

const DARK_C = {
  bg: "#26364A",
  surface: "#304158",
  sidebar: "#202B3D",
  green: "#20D99A",
  greenDark: "#20D99A",
  teal: "#00B8C8",
  cyan: "#72D4D7",
  mint: "#304158",
  mint2: "#304158",
  border: "#40536A",
  text: "#F5FFFD",
  muted: "#A9BBC2",
  muted2: "#A9BBC2",
  danger: "#FF7B7B",
  warning: "#F2C75C",
  high: "#FF9A5C",
  white: "#F5FFFD",
};

type ThemeColors = typeof LIGHT_C;
let C: ThemeColors = LIGHT_C;
let styles: any;

/* ============================================================
 * A PI CONFIG  *
 * ============================================================ */

const backend =
Constants.expoConfig?.extra?.backendUrl ||
process.env.EXPO_PUBLIC_BACKEND_URL ||
process.env.EXPO_BACKEND_URL ||
"http://localhost:8000";

  const API = `${backend.replace(/\/$/, "")}/api`;

  const GOOGLE_MAPS_API_KEY =
  process.env.EXPO_PUBLIC_GOOGLE_MAPS_API_KEY || "";

  /* ============================================================
   *   T YPES       *
   *   ============================================================ */

  type User = {
    user_id?: string;
    full_name: string;
    email: string;
    account_type: string;
    organization?: string;
    role: string;
    institution?: string;
    research_area?: string;
    created_at: string;
  };

  type Dataset = {
    dataset_id: string;
    user_id?: string;
    source_type?: string;
    filename: string;
    file_type: string;
    imported_at: string;
    columns: string[];
    records: Record<string, any>[];
    quality: {
      score?: number;
      type?: string;
      label?: string;
      status?: string;
      missing?: number;
      analysis_issues?: number;
      coordinate_issues?: number;
      duplicates?: number;
      valid_records?: number;
      invalid_records?: number;
      engine_report?: any;
      [key: string]: any;
    };
    data_source?: string;
    laboratory_organization?: string;
    report_id?: string;
    analytical_method?: string;
    detection_limit?: string;
  };

  type Page =
  | "dashboard"
  | "import"
  | "quality"
  | "analysis"
  | "spatial"
  | "reports"
  | "profile";

  /* ============================================================
   *   N AVIGATION  *
   *   ============================================================ */

  const NAV: {
    id: Page;
    label: string;
    icon: keyof typeof Ionicons.glyphMap;
  }[] = [
    {
      id: "dashboard",
      label: "Dashboard",
      icon: "grid-outline",
    },
{
  id: "import",
  label: "Data Import",
  icon: "cloud-upload-outline",
},
{
  id: "quality",
  label: "Data Quality",
  icon: "shield-checkmark-outline",
},
{
  id: "analysis",
  label: "Pollution Analysis",
  icon: "analytics-outline",
},
{
  id: "spatial",
  label: "Spatial & Temporal",
  icon: "map-outline",
},
{
  id: "reports",
  label: "Reports & Decisions",
  icon: "document-text-outline",
},
{
  id: "profile",
  label: "Profile",
  icon: "person-outline",
},
  ];

  /* ============================================================
   *   A PI HELPER  *
   *   ============================================================ */

  async function api(
    path: string,
    options: RequestInit = {},
    token?: string,
  ) {
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string> | undefined),
    };

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(`${API}${path}`, {
      ...options,
      headers,
    });

    const text = await response.text();

    let body: any = {};

    try {
      body = text ? JSON.parse(text) : {};
    } catch {
      body = {
        message: text,
      };
    }

    if (!response.ok) {
      let message = "Something went wrong";

      if (typeof body?.detail === "string") {
        message = body.detail;
      } else if (body?.detail?.message) {
        message = body.detail.message;
      } else if (Array.isArray(body?.detail?.errors)) {
        message = body.detail.errors
        .map(
          (error: any) =>
          `Row ${error?.row ?? "?"}: ${
            error?.problem ?? "Validation error"
          }`,
        )
        .join("\n");
      } else if (body?.detail) {
        message = JSON.stringify(
          body.detail,
          null,
          2,
        );
      } else if (body?.message) {
        message = body.message;
      }

      throw new Error(
        `${response.status}: ${message}`,
      );
    }

    return body;
  }

  /* ============================================================
   *   A NALYSIS API* TYPES
   *   ============================================================ */

  type AnalysisSummary = {
    dataset_id: string;
    record_count: number;
    average_hpi: number | null;
    average_hei: number | null;
    average_cd: number | null;
    max_hpi: number | null;
    min_hpi: number | null;
    overall_status: string;
    high_samples: number;
    moderate_samples: number;
    low_samples: number;
    safe_samples: number;
    quality_score: number | null;
  };

  type MetalAnalysis = {
    metal: string;
    sample_count: number;
    average_measured: number | null;
    maximum_measured: number | null;
    average_ratio: number | null;
    maximum_exceedance: number | null;
    high_samples: number;
  };

  type SpatialPoint = {
    sample_id: string;
    latitude: number;
    longitude: number;
    country?: string;
    region?: string;
    area?: string;
    water_body?: string;
    water_type?: string;
    date?: string | null;
    hpi?: number | null;
    hei?: number | null;
    cd?: number | null;
    status?: string;
    highest_metal?: string | null;
    standard?: string;
    authority?: string;
  };

  type SpatialResponse = {
    dataset_id: string;
    points: SpatialPoint[];
    count: number;
  };

  type MapPoint = SpatialPoint & {
    risk_score?: number;
  };

  type MapPointsResponse = {
    dataset_id: string;
    points: MapPoint[];
    count: number;
  };

  type MapSummary = {
    dataset_id: string;
    count: number;
    high_risk_count: number;
    moderate_count: number;
    low_risk_count: number;
    safe_count: number;
    center?: {
      latitude: number;
      longitude: number;
    } | null;
    bounds?: {
      north: number;
      south: number;
      east: number;
      west: number;
    } | null;
  };

  type MapHotspot = {
    hotspot_id: string;
    center: {
      latitude: number;
      longitude: number;
    };
    sample_count: number;
    samples: string[];
    max_risk_score: number;
    average_hpi: number | null;
    radius_km: number;
  };

  type MapHotspotsResponse = {
    dataset_id: string;
    radius_km: number;
    hotspots: MapHotspot[];
    count: number;
  };

  /* ============================================================
   *   H ELPERS     *
   *   ============================================================ */

  function initials(name = "") {
    return (
      name.trim().charAt(0).toUpperCase() || "U"
    );
  }

  function prettyDate(value?: string) {
    if (!value) {
      return "Not provided";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return date.toLocaleDateString();
  }

  function firstNumber(
    row: Record<string, any>,
    names: string[],
  ) {
    for (const name of names) {
      const key = Object.keys(row).find(
        (k) =>
        k
        .toLowerCase()
        .replace(/[^a-z0-9]/g, "") ===
        name
        .toLowerCase()
        .replace(/[^a-z0-9]/g, ""),
      );

      if (
        key != null &&
        row[key] !== "" &&
        row[key] != null
      ) {
        const value = Number(row[key]);

        if (Number.isFinite(value)) {
          return value;
        }
      }
    }

    return 0;
  }

  function statusColor(status: string) {
    const normalized =
    String(status || "UNKNOWN").toUpperCase();

    if (
      normalized === "HIGH" ||
      normalized === "CRITICAL"
    ) {
      return C.high;
    }

    if (normalized === "MODERATE") {
      return C.warning;
    }

    if (
      normalized === "LOW" ||
      normalized === "SAFE"
    ) {
      return C.green;
    }

    return C.muted;
  }

  const TEMPLATE_FIELDS = [
    { key: "Sample_ID", required: true, description: "Unique identifier for the water quality sample." },
{ key: "Sampling_Date", required: true, description: "Sampling date in YYYY-MM-DD format." },
{ key: "Season", required: false, description: "Season during which the sample was collected." },
{ key: "Water_Type", required: true, description: "Type or source of water, such as Groundwater or Surface Water." },
{ key: "Location_Name", required: true, description: "Human-readable monitoring location name." },
{ key: "Latitude", required: true, description: "Sampling latitude in decimal degrees." },
{ key: "Longitude", required: true, description: "Sampling longitude in decimal degrees." },
{ key: "Intended_Use", required: true, description: "Intended use such as Drinking Water, Irrigation, or Industrial." },
{ key: "pH", required: true, description: "Measured pH value of the sample." },
{ key: "Temperature_C", required: false, description: "Water temperature in degrees Celsius." },
{ key: "Electrical_Conductivity", required: false, description: "Electrical conductivity of the sample." },
{ key: "TDS_mg_L", required: false, description: "Total dissolved solids concentration in mg/L." },
{ key: "Dissolved_Oxygen_mg_L", required: false, description: "Dissolved oxygen concentration in mg/L." },
{ key: "Turbidity_NTU", required: false, description: "Turbidity measured in NTU." },
{ key: "Metal_Unit", required: true, description: "Unit used for the heavy-metal concentration columns, for example mg/L." },
{ key: "Iron_Fe_mg_L", required: false, description: "Iron concentration in mg/L." },
{ key: "Manganese_Mn_mg_L", required: false, description: "Manganese concentration in mg/L." },
{ key: "Copper_Cu_mg_L", required: false, description: "Copper concentration in mg/L." },
{ key: "Zinc_Zn_mg_L", required: false, description: "Zinc concentration in mg/L." },
{ key: "Lead_Pb_mg_L", required: false, description: "Lead concentration in mg/L." },
{ key: "Cadmium_Cd_mg_L", required: false, description: "Cadmium concentration in mg/L." },
{ key: "Chromium_Cr_mg_L", required: false, description: "Chromium concentration in mg/L." },
{ key: "Nickel_Ni_mg_L", required: false, description: "Nickel concentration in mg/L." },
{ key: "Arsenic_As_mg_L", required: false, description: "Arsenic concentration in mg/L." },
{ key: "Mercury_Hg_mg_L", required: false, description: "Mercury concentration in mg/L." },
{ key: "Remarks", required: false, description: "Optional observations, laboratory notes, or sample remarks." },
  ];

  const TEMPLATE_SAMPLE_ROW = [
    "WQ001",
"2025-01-15",
"Winter",
"Groundwater",
"Kalyan Station Well",
"19.2437",
"73.1305",
"Drinking Water",
"7.2",
"28.5",
"420",
"250",
"6.8",
"3.1",
"mg/L",
"0.15",
"0.03",
"0.02",
"0.08",
"0.001",
"0.0005",
"0.004",
"0.006",
"0.002",
"0.0001",
"Sample within permissible limits",
  ];

  const TEMPLATE_HEADERS = TEMPLATE_FIELDS.map((field) => field.key);

  const SUPPORTED_METALS = [
    "Pb",
"Cd",
"As",
"Cr",
"Hg",
"Ni",
"Cu",
"Zn",
"Fe",
"Mn",
  ];

  function normaliseKey(value = "") {
    return value.toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  function findField(
    row: Record<string, any>,
    names: string[],
  ) {
    const wanted = names.map(normaliseKey);
    const key = Object.keys(row).find((candidate) =>
    wanted.includes(normaliseKey(candidate)),
    );
    return key ? row[key] : undefined;
  }

  function sampleIdFor(
    row: Record<string, any>,
    index: number,
  ) {
    return String(
      findField(row, ["sample_id", "sample", "id"]) ||
      `S${String(index + 1).padStart(3, "0")}`,
    );
  }

  function sampleDateFor(row: Record<string, any>) {
    return findField(row, [
      "date",
      "sample_date",
      "sampleDate",
      "datetime",
      "date_time",
      "timestamp",
    ]);
  }

  function metalKeysFor(row: Record<string, any>) {
    return Object.keys(row).filter((key) =>
    SUPPORTED_METALS.some(
      (metal) =>
      normaliseKey(key) === normaliseKey(metal),
    ),
    );
  }

  function rowLabel(
    row: Record<string, any>,
    names: string[],
  ) {
    const value = findField(row, names);
    return value == null || value === ""
    ? ""
    : String(value);
  }

  function getQualityChecks(dataset?: Dataset) {
    const records = dataset?.records || [];
    const quality = dataset?.quality || {};
    const ids = records.map(sampleIdFor);
    const seen = new Set<string>();
    const duplicateIds = new Set<string>();

    ids.forEach((id) => {
      if (seen.has(id)) duplicateIds.add(id);
      seen.add(id);
    });

    let missingValues = 0;
    let invalidUnits = 0;
    let invalidCoordinates = 0;
    let missingDates = 0;
    const numericValues: number[] = [];
    const rowNumericValues: number[][] = [];

    records.forEach((row) => {
      const lat = findField(row, ["latitude", "lat"]);
      const lon = findField(row, ["longitude", "lon", "lng"]);
      const metals = metalKeysFor(row);
      const hasMetal = metals.some(
        (key) =>
        row[key] !== "" &&
        row[key] != null &&
        Number.isFinite(Number(row[key])),
      );

      if (
        lat === "" ||
        lat == null ||
        lon === "" ||
        lon == null ||
        !Number.isFinite(Number(lat)) ||
        !Number.isFinite(Number(lon))
      ) {
        invalidCoordinates += 1;
      }

      if (!hasMetal) {
        missingValues += 1;
      }

      const date = sampleDateFor(row);
      if (date === "" || date == null) {
        missingDates += 1;
      }

      const rowValues: number[] = [];
      metals.forEach((key) => {
        const raw = row[key];
        if (raw === "" || raw == null) return;
        const value = Number(raw);
        if (!Number.isFinite(value) || value < 0) {
          invalidUnits += 1;
        } else {
          numericValues.push(value);
          rowValues.push(value);
        }
      });
      rowNumericValues.push(rowValues);
    });

    const mean =
    numericValues.length > 0
    ? numericValues.reduce((sum, value) => sum + value, 0) /
    numericValues.length
    : 0;
    const variance =
    numericValues.length > 1
    ? numericValues.reduce(
      (sum, value) => sum + Math.pow(value - mean, 2),
                           0,
    ) / numericValues.length
    : 0;
    const std = Math.sqrt(variance);

    let outliers = 0;
    if (std > 0) {
      outliers = rowNumericValues.filter((values) =>
      values.some(
        (value) => Math.abs(value - mean) / std > 2,
      ),
      ).length;
    }

    const countOrFallback = (
      value: any,
      fallback: number,
    ) =>
    Number.isFinite(Number(value))
    ? Number(value)
    : fallback;

    return [
      {
        label: "Missing values",
        count: countOrFallback(
          quality.missing,
          missingValues,
        ),
        icon: "remove-circle-outline" as keyof typeof Ionicons.glyphMap,
      },
      {
        label: "Invalid / out-of-range units",
        count: invalidUnits,
        icon: "flask-outline" as keyof typeof Ionicons.glyphMap,
      },
      {
        label: "Duplicate sample IDs",
        count: countOrFallback(
          quality.duplicates,
          duplicateIds.size,
        ),
        icon: "copy-outline" as keyof typeof Ionicons.glyphMap,
      },
      {
        label: "Invalid or missing coordinates",
        count: countOrFallback(
          quality.coordinate_issues,
          invalidCoordinates,
        ),
        icon: "navigate-outline" as keyof typeof Ionicons.glyphMap,
      },
      {
        label: "Missing sample dates",
        count: missingDates,
        icon: "calendar-outline" as keyof typeof Ionicons.glyphMap,
      },
      {
        label: "Statistical outliers (z-score > 2σ)",
        count: outliers,
        icon: "stats-chart-outline" as keyof typeof Ionicons.glyphMap,
      },
    ];
  }

  /* ============================================================
   *   B ACKEND ANAL*YSIS DATA
   *   ============================================================ */

  function sampleMetrics(dataset?: Dataset) {
    if (!dataset) {
      return [];
    }

    return (dataset.records || []).map(
      (row, index) => {
        const analysis =
        row?.analysis || {};

        const hpi = Number(
          analysis.hpi,
        );

        const hei = Number(
          analysis.hei,
        );

        const cd = Number(
          analysis.cd,
        );

        return {
          row,

          id: sampleIdFor(row, index),

                                       hpi:
                                       Number.isFinite(hpi)
                                       ? hpi
                                       : 0,

                                       hei:
                                       Number.isFinite(hei)
                                       ? hei
                                       : 0,

                                       cd:
                                       Number.isFinite(cd)
                                       ? cd
                                       : 0,

                                       lat:
                                       firstNumber(
                                         row,
                                         ["latitude", "lat"],
                                       ),

                                       lon:
                                       firstNumber(
                                         row,
                                         [
                                           "longitude",
                                           "lon",
                                           "lng",
                                         ],
                                       ),

                                       status:
                                       String(
                                         analysis.status ||
                                         "UNKNOWN",
                                       ).toUpperCase(),
        };
      },
    );
  }

  /* ============================================================
   *   R OOT        *
   *   ============================================================ */

  export default function Index() {
    const [
      token,
      setToken,
    ] = useState<string | null>(null);

    const [
      user,
      setUser,
    ] = useState<User | null>(null);

    const [
      datasets,
      setDatasets,
    ] = useState<Dataset[]>([]);

    const [
      page,
      setPage,
    ] = useState<Page>("dashboard");

    const [
      authMode,
      setAuthMode,
    ] = useState<
    "login" | "signup"
    >("login");

    const [
      loading,
      setLoading,
    ] = useState(true);

    const [
      isDark,
      setIsDark,
    ] = useState(false);

    const toggleTheme = () => {
      const next = !isDark;
      C = next ? DARK_C : LIGHT_C;
      styles = createStyles();
      setIsDark(next);
    };

    useEffect(() => {
      let mounted = true;

      AsyncStorage.multiGet([
        "ms_token",
        "ms_user",
      ])
      .then(
        ([tokenItem, userItem]) => {
          if (!mounted) {
            return;
          }

          const savedToken =
          tokenItem?.[1];

          const savedUser =
          userItem?.[1];

          if (
            savedToken &&
            savedUser &&
            savedUser !==
            "undefined" &&
            savedUser !== "null"
          ) {
            try {
              setToken(
                savedToken,
              );

              setUser(
                JSON.parse(
                  savedUser,
                ),
              );
            } catch {
              AsyncStorage.multiRemove([
                "ms_token",
                "ms_user",
              ]);
            }
          }

          setLoading(false);
        },
      )
      .catch(() => {
        if (mounted) {
          setLoading(false);
        }
      });

      return () => {
        mounted = false;
      };
    }, []);

    const refresh = async (
      currentToken = token,
    ) => {
      if (!currentToken) {
        return;
      }

      try {
        const data = await api(
          "/datasets",
          {},
          currentToken,
        );

        setDatasets(
          Array.isArray(data)
          ? data
          : data?.datasets || [],
        );
      } catch {
        await signOut();
      }
    };

    useEffect(() => {
      if (token) {
        refresh(token);
      }
    }, [token]);

    const signIn = async (
      result: any,
    ) => {
      if (
        !result?.token ||
        !result?.user
      ) {
        throw new Error(
          "The server returned an invalid login response.",
        );
      }

      setToken(
        result.token,
      );

      setUser(
        result.user,
      );

      setPage("dashboard");

      await AsyncStorage.multiSet([
        [
          "ms_token",
          result.token,
        ],
        [
          "ms_user",
          JSON.stringify(
            result.user,
          ),
        ],
      ]);
    };

    const signOut = async () => {
      setToken(null);
      setUser(null);
      setDatasets([]);
      setPage("dashboard");

      await AsyncStorage.multiRemove([
        "ms_token",
        "ms_user",
      ]);
    };

    if (loading) {
      return (
        <View
        style={
          styles.center
        }
        >
        <ActivityIndicator
        color={
          C.green
        }
        size="large"
        />
        </View>
      );
    }

    if (!token || !user) {
      return (
        <Auth
        mode={
          authMode
        }
        setMode={
          setAuthMode
        }
        onSuccess={
          signIn
        }
        isDark={
          isDark
        }
        toggleTheme={
          toggleTheme
        }
        />
      );
    }

    const activeDataset =
    datasets[0];

    return (
      <AppShell
      page={page}
      setPage={setPage}
      user={user}
      datasets={
        datasets
      }
      activeDataset={
        activeDataset
      }
      token={token}
      refresh={
        refresh
      }
      signOut={
        signOut
      }
      isDark={
        isDark
      }
      toggleTheme={
        toggleTheme
      }
      />
    );
  }

  /* ============================================================
   *   A UTH        *
   *   ============================================================ */

  function Auth({
    mode,
    setMode,
    onSuccess,
    isDark,
    toggleTheme,
  }: {
    mode:
    | "login"
    | "signup";

    setMode: (
      value:
      | "login"
      | "signup",
    ) => void;

    onSuccess: (
      value: any,
    ) => Promise<void>;

    isDark: boolean;
    toggleTheme: () => void;
  }) {
    const [
      form,
        setForm,
    ] = useState<
    Record<string, string>
    >({});

    const [
      busy,
      setBusy,
    ] = useState(false);

    const [
      show,
      setShow,
    ] = useState(false);

    const [
      error,
      setError,
    ] = useState("");

    const update = (
      key: string,
      value: string,
    ) => {
      setForm(
        (old) => ({
          ...old,
          [key]: value,
        }),
      );
    };

    const submit = async () => {
      setError("");

      if (
        !form.email ||
        !form.password ||
        (
          mode === "signup" &&
          (
            !form.full_name ||
            !form.role ||
            !form.account_type
          )
        )
      ) {
        setError(
          "Complete all required fields.",
        );

        return;
      }

      if (
        mode === "signup" &&
        form.password !==
          form.confirm
      ) {
        setError(
          "Passwords do not match.",
        );

        return;
      }

      setBusy(true);

      try {
        const result =
        await api(
          mode === "login"
          ? "/auth/login"
          : "/auth/signup",
          {
            method:
            "POST",
            headers: {
              "Content-Type":
              "application/json",
            },
            body:
            JSON.stringify({
              ...form,

              organization:
              form.organization ||
                "",

                institution:
                form.institution ||
                  "",

                  research_area:
                  form.research_area ||
                    "",
            }),
          },
        );

        await onSuccess(
          result,
        );
      } catch (
        error: any
      ) {
        setError(
          error?.message ||
          "Unable to continue.",
        );
      } finally {
        setBusy(false);
      }
    };

    return (
      <KeyboardAvoidingView
      style={
        styles.authWrap
      }
      behavior={
        Platform.OS ===
        "ios"
        ? "padding"
        : undefined
      }
      >
      <ScrollView
      contentContainerStyle={
        styles.authScroll
      }
      keyboardShouldPersistTaps="handled"
      >
      <View
      style={
        styles.brand
      }
      >
      <Image
      source={require("../metalsense.png")}
      style={styles.sidebarLogo}
      />

      <Text
      style={
        styles.brandName
      }
      >
      MetalSense
      </Text>

      <Text
      style={
        styles.tagline
      }
      >
      Heavy Metal Pollution
      Intelligence
      </Text>
      </View>

      <Pressable
      onPress={toggleTheme}
      style={styles.authThemeToggle}
      >
      <Ionicons
      name={isDark ? "sunny-outline" : "moon-outline"}
      size={17}
      color={C.teal}
      />
      <Text style={styles.authThemeToggleText}>
      {isDark ? "Light mode" : "Dark mode"}
      </Text>
      </Pressable>

      <View
      style={
        styles.authCard
      }
      >
      <Text
      style={
        styles.eyebrow
      }
      >
      SECURE WORKSPACE
      </Text>

      <Text
      style={
        styles.h1
      }
      >
      {mode ===
        "login"
        ? "Welcome back"
        : "Create your account"}
        </Text>

        <Text
        style={
          styles.sub
        }
        >
        {mode ===
          "login"
          ? "Continue to your water quality intelligence workspace."
          : "Set up a professional workspace for traceable analysis."}
          </Text>

          {mode ===
            "signup" && (
              <>
              <Field
              label="FULL NAME *"
              value={
                form.full_name ||
                  ""
              }
              onChangeText={(
                value,
              ) =>
              update(
                "full_name",
                value,
              )
              }
              placeholder="Your name"
              />

              <Field
              label="ACCOUNT TYPE *"
              value={
                form.account_type ||
                  ""
              }
              onChangeText={(
                value,
              ) =>
              update(
                "account_type",
                value,
              )
              }
              placeholder="Student / Researcher / Organization"
              />

              <Field
              label="ROLE *"
              value={
                form.role ||
                  ""
              }
              onChangeText={(
                value,
              ) =>
              update(
                "role",
                value,
              )
              }
              placeholder="analyst"
              />

              <Field
              label="ORGANIZATION"
              value={
                form.organization ||
                  ""
              }
              onChangeText={(
                value,
              ) =>
              update(
                "organization",
                value,
              )
              }
              placeholder="Organization"
              />

              <Field
              label="INSTITUTION"
              value={
                form.institution ||
                  ""
              }
              onChangeText={(
                value,
              ) =>
              update(
                "institution",
                value,
              )
              }
              placeholder="Institution"
              />

              <Field
              label="RESEARCH AREA"
              value={
                form.research_area ||
                  ""
              }
              onChangeText={(
                value,
              ) =>
              update(
                "research_area",
                value,
              )
              }
              placeholder="Water Quality"
              />
              </>
            )}

            <Field
            label="EMAIL *"
            value={
              form.email ||
                ""
            }
            onChangeText={(
              value,
            ) =>
            update(
              "email",
              value,
            )
            }
            placeholder="you@example.com"
            keyboardType="email-address"
            autoCapitalize="none"
            />

            <View>
            <Text
            style={
              styles.fieldLabel
            }
            >
            PASSWORD *
            </Text>

            <View
            style={
              styles.passwordBox
            }
            >
            <TextInput
            value={
              form.password ||
                ""
            }
            onChangeText={(
              value,
            ) =>
            update(
              "password",
              value,
            )
            }
            placeholder="Password"
            placeholderTextColor={
              C.muted
            }
            secureTextEntry={
              !show
            }
            style={
              styles.passwordInput
            }
            autoCapitalize="none"
            />

            <Pressable
            onPress={() =>
              setShow(
                (old) =>
                !old,
              )
            }
            >
            <Ionicons
            name={
              show
              ? "eye-off-outline"
              : "eye-outline"
            }
            size={21}
            color={
              C.muted
            }
            />
            </Pressable>
            </View>
            </View>

            {mode ===
              "signup" && (
                <Field
                label="CONFIRM PASSWORD *"
                value={
                  form.confirm ||
                    ""
                }
                onChangeText={(
                  value,
                ) =>
                update(
                  "confirm",
                  value,
                )
                }
                placeholder="Confirm password"
                secureTextEntry
                />
              )}

              {!!error && (
                <Text
                style={
                  styles.authError
                }
                >
                {error}
                </Text>
              )}

              <Pressable
              style={({
                pressed,
              }) => [
                styles.primaryButton,
                pressed && {
                  opacity: 0.82,
                },
                busy && {
                  opacity: 0.6,
                },
              ]}
              onPress={
                submit
              }
              disabled={
                busy
              }
              >
              {busy ? (
                <ActivityIndicator
                color={C.white}
                />
              ) : (
                <>
                <Text
                style={
                  styles.primaryButtonText
                }
                >
                {mode ===
                  "login"
                  ? "Sign in"
                  : "Create account"}
                  </Text>

                  <Ionicons
                  name="arrow-forward"
                  size={19}
                  color={C.white}
                  />
                  </>
              )}
              </Pressable>

              <Pressable
              onPress={() => {
                setError("");

                setMode(
                  mode ===
                  "login"
                  ? "signup"
                  : "login",
                );
              }}
              >
              <Text
              style={
                styles.authSwitch
              }
              >
              {mode ===
                "login"
                ? "Don't have an account? Sign up"
                : "Already have an account? Sign in"}
                </Text>
                </Pressable>
                </View>
                </ScrollView>
                </KeyboardAvoidingView>
    );
  }

  /* ============================================================
   *   F IELD       *
   *   ============================================================ */

  function Field({
    label,
    value,
    onChangeText,
    placeholder,
    secureTextEntry,
    keyboardType,
    autoCapitalize,
    compact,
  }: {
    label: string;
    value: string;
    onChangeText: (
      value: string,
    ) => void;
    placeholder?: string;
    secureTextEntry?: boolean;
    keyboardType?: any;
    autoCapitalize?: any;
    compact?: boolean;
  }) {
    return (
      <View
      style={[
        styles.fieldWrap,
        compact && styles.metadataGridField,
      ]}
      >
      <Text
      style={
        styles.fieldLabel
      }
      >
      {label}
      </Text>

      <TextInput
      value={value}
      onChangeText={
        onChangeText
      }
      placeholder={
        placeholder
      }
      placeholderTextColor={
        C.muted
      }
      secureTextEntry={
        secureTextEntry
      }
      keyboardType={
        keyboardType
      }
      autoCapitalize={
        autoCapitalize
      }
      style={
        styles.input
      }
      />
      </View>
    );
  }

  /* ============================================================
   *   A PP SHELL   *
   *   ============================================================ */

  function AppShell({
    page,
    setPage,
    user,
    datasets,
    activeDataset,
    token,
    refresh,
    signOut,
    isDark,
    toggleTheme,
  }: {
    page: Page;
    setPage: (
      page: Page,
    ) => void;
    user: User;
    datasets: Dataset[];
    activeDataset?: Dataset;
    token: string;
    refresh: (
      token?: string,
    ) => Promise<void>;
    signOut: () => Promise<void>;
    isDark: boolean;
    toggleTheme: () => void;
  }) {
    const [
      menuOpen,
      setMenuOpen,
    ] = useState(false);

    const title =
    NAV.find(
      (item) =>
      item.id ===
      page,
    )?.label ||
    "Dashboard";

          return (
            <View
            style={
              styles.shell
            }
            >
            <View
            style={[
              styles.sidebar,
              menuOpen &&
              styles.sidebarMobile,
            ]}
            >
            <View
            style={
              styles.sidebarBrand
            }
            >
            <Image
            source={require("../metalsense.png")}
            style={styles.sidebarLogo}
            />

            <Text
            style={
              styles.sidebarBrandText
            }
            >
            MetalSense
            </Text>
            </View>

            <Text
            style={
              styles.workspaceLabel
            }
            >
            WORKSPACE
            </Text>

            <View
            style={
              styles.navList
            }
            >
            {NAV.map(
              (item) => (
                <Pressable
                key={
                  item.id
                }
                onPress={() => {
                  setPage(
                    item.id,
                  );
                  setMenuOpen(
                    false,
                  );
                }}
                style={({
                  pressed,
                }) => [
                  styles.navItem,
                  page ===
                  item.id &&
                  styles.navItemActive,
                  pressed && {
                    opacity: 0.8,
                  },
                ]}
                >
                <Ionicons
                name={
                  item.icon
                }
                size={19}
                color={
                  page ===
                  item.id
                  ? C.green
                  : C.muted
                }
                />

                <Text
                style={[
                  styles.navText,
                  page ===
                  item.id &&
                  styles.navTextActive,
                ]}
                >
                {item.label}
                </Text>
                </Pressable>
              ),
            )}
            </View>

            <View
            style={
              styles.sidebarBottom
            }
            >
            <View
            style={
              styles.sidebarDivider
            }
            />

            <View
            style={
              styles.userMini
            }
            >
            <View
            style={
              styles.avatarSmall
            }
            >
            <Text
            style={
              styles.avatarLetter
            }
            >
            {initials(
              user.full_name,
            )}
            </Text>
            </View>

            <View
            style={{
              flex: 1,
            }}
            >
            <Text
            style={
              styles.userMiniName
            }
            >
            {
              user.full_name
            }
            </Text>

            <Text
            style={
              styles.userMiniRole
            }
            >
            {
              user.role
            }
            </Text>
            </View>

            <Pressable
            onPress={
              signOut
            }
            >
            <Ionicons
            name="log-out-outline"
            size={20}
            color={
              C.muted
            }
            />
            </Pressable>
            </View>
            </View>
            </View>

            <View
            style={
              styles.main
            }
            >
            <View
            style={
              styles.topbar
            }
            >
            <Pressable
            style={
              styles.mobileMenu
            }
            onPress={() =>
              setMenuOpen(
                (old) =>
                !old,
              )
            }
            >
            <Ionicons
            name="menu-outline"
            size={24}
            color={
              C.text
            }
            />
            </Pressable>

            <View
            style={
              styles.topbarTitle
            }
            >
            <Ionicons
            name="water"
            size={20}
            color={
              C.teal
            }
            />

            <View>
            <Text
            style={
              styles.topTitle
            }
            >
            {title}
            </Text>

            <Text
            style={
              styles.topSubtitle
            }
            >
            Welcome,{" "}
            {
              user.full_name
            }{" "}
            ·{" "}
            {
              user.role
            }
            </Text>
            </View>
            </View>

            <Pressable
            onPress={toggleTheme}
            style={styles.themeToggle}
            accessibilityRole="button"
            accessibilityLabel={
              isDark ? "Switch to light mode" : "Switch to dark mode"
            }
            >
            <Ionicons
            name={isDark ? "sunny-outline" : "moon-outline"}
            size={18}
            color={C.teal}
            />
            <Text style={styles.themeToggleText}>
            {isDark ? "Light" : "Dark"}
            </Text>
            </Pressable>

            <View
            style={
              styles.topAvatar
            }
            >
            <Text
            style={
              styles.topAvatarText
            }
            >
            {initials(
              user.full_name,
            )}
            </Text>
            </View>
            </View>

            <ScrollView
            style={
              styles.content
            }
            contentContainerStyle={
              styles.contentInner
            }
            showsVerticalScrollIndicator
            >
            {page ===
              "dashboard" && (
                <Dashboard
                user={
                  user
                }
                datasets={
                  datasets
                }
                token={
                  token
                }
                setPage={
                  setPage
                }
                />
              )}

              {page ===
                "import" && (
                  <ImportScreen
                  datasets={
                    datasets
                  }
                  token={
                    token
                  }
                  refresh={
                    refresh
                  }
                  />
                )}

                {page ===
                  "quality" && (
                    <QualityScreen
                    dataset={
                      activeDataset
                    }
                    />
                  )}

                  {page ===
                    "analysis" && (
                      <AnalysisScreen
                      dataset={
                        activeDataset
                      }
                      token={
                        token
                      }
                      />
                    )}

                    {page ===
                      "spatial" && (
                        <SpatialScreen
                        dataset={
                          activeDataset
                        }
                        token={
                          token
                        }
                        />
                      )}

                      {page ===
                        "reports" && (
                          <ReportsScreen
                          dataset={
                            activeDataset
                          }
                          datasets={
                            datasets
                          }
                          user={
                            user
                          }
                          />
                        )}

                        {page ===
                          "profile" && (
                            <ProfileScreen
                            user={
                              user
                            }
                            signOut={
                              signOut
                            }
                            />
                          )}
                          </ScrollView>
                          </View>
                          </View>
          );
  }

  /* ============================================================
   *   P AGE INTRO  *
   *   ============================================================ */

  function PageIntro({
    eyebrow,
    title,
    description,
  }: {
    eyebrow: string;
    title: string;
    description: string;
  }) {
    return (
      <View
      style={
        styles.pageIntro
      }
      >
      <Text
      style={
        styles.pageEyebrow
      }
      >
      {eyebrow}
      </Text>

      <Text
      style={
        styles.pageTitle
      }
      >
      {title}
      </Text>

      <Text
      style={
        styles.pageDescription
      }
      >
      {description}
      </Text>
      </View>
    );
  }

  /* ============================================================
   *   D ASHBOARD   *
   *   ============================================================ */

  function Dashboard({
    datasets,
    token,
    setPage,
  }: {
    user: User;
    datasets: Dataset[];
    token: string;
    setPage: (
      page: Page,
    ) => void;
  }) {
    const dataset =
    datasets[0];

    const [summary, setSummary] =
    useState<AnalysisSummary | null>(null);

    const [loadingSummary, setLoadingSummary] =
    useState(false);

    useEffect(() => {
      let active = true;

      if (!dataset?.dataset_id || !token) {
        setSummary(null);
        return () => {
          active = false;
        };
      }

      setLoadingSummary(true);

      api(
        `/analysis/${dataset.dataset_id}/summary`,
        {},
        token,
      )
      .then((data) => {
        if (active) {
          setSummary(data);
        }
      })
      .catch((error) => {
        console.error('Dashboard summary failed:', error);
        if (active) {
          setSummary(null);
        }
      })
      .finally(() => {
        if (active) {
          setLoadingSummary(false);
        }
      });

      return () => {
        active = false;
      };
    }, [dataset?.dataset_id, token]);

    const metrics = sampleMetrics(dataset);

    const samples =
    summary?.record_count ??
    metrics.length;

    const critical =
    summary?.high_samples ??
    metrics.filter(
      (item) => item.status === 'HIGH',
    ).length;

    const locations =
    new Set(
      metrics.map(
        (item) =>
        `${item.lat.toFixed(5)},${item.lon.toFixed(5)}`,
      ),
    ).size;

    return (
      <View>
      <View
      style={
        styles.heroCard
      }
      >
      <View
      style={{
        flex: 1,
      }}
      >
      <Text
      style={
        styles.heroEyebrow
      }
      >
      METALSENSE
      INTELLIGENCE
      </Text>

      <Text
      style={
        styles.heroTitle
      }
      >
      A clearer view
      of water quality.
      </Text>

      <Text
      style={
        styles.heroText
      }
      >
      Validate evidence,
      trace standards,
      and understand
      heavy-metal risk
      without losing
      provenance.
      </Text>
      </View>

      <Pressable
      style={
        styles.importButton
      }
      onPress={() =>
        setPage("import")
      }
      >
      <Ionicons
      name="cloud-upload-outline"
      size={19}
      color={C.white}
      />

      <Text
      style={
        styles.importButtonText
      }
      >
      Import dataset
      </Text>
      </Pressable>
      </View>

      <View
      style={
        styles.statRow
      }
      >
      <StatCard
      icon="flask-outline"
      value={
        samples
      }
      label="Samples"
      />

      <StatCard
      icon="documents-outline"
      value={
        datasets.length
      }
      label="Files"
      />

      <StatCard
      icon="location-outline"
      value={
        locations ||
        0
      }
      label="Locations"
      />
      </View>

      <View
      style={
        styles.singleStat
      }
      >
      <Ionicons
      name="alert-circle-outline"
      size={21}
      color={
        C.danger
      }
      />

      <Text
      style={
        styles.bigStat
      }
      >
      {
        critical
      }
      </Text>

      <Text
      style={
        styles.statLabel
      }
      >
      Critical samples
      </Text>
      </View>

      <View
      style={
        styles.panel
      }
      >
      <Text
      style={
        styles.panelTitle
      }
      >
      Latest imported
      evidence
      </Text>

      <Text
      style={
        styles.panelSubtitle
      }
      >
      {
        samples
      }{" "}
      validated samples
      </Text>

      {loadingSummary && (
        <View style={styles.loadingBanner}>
        <ActivityIndicator color={C.green} />
        <Text style={styles.loadingText}>Refreshing analysis summary…</Text>
        </View>
      )}

      {metrics.length ===
        0 ? (
          <EmptyState
          icon="flask-outline"
          title="No monitoring data yet"
          text="Import a CSV or Excel workbook to begin."
          />
        ) : (
          metrics
          .slice(0, 8)
          .map(
            (
              item,
            ) => (
              <SampleRow
              key={
                item.id
              }
              item={
                item
              }
              />
            ),
          )
        )}
        </View>
        </View>
    );
  }

  /* ============================================================
   *   S TAT CARD   *
   *   ============================================================ */

  function StatCard({
    icon,
    value,
    label,
  }: {
    icon: keyof typeof Ionicons.glyphMap;
    value:
    | number
    | string;
    label: string;
  }) {
    return (
      <View
      style={
        styles.statCard
      }
      >
      <Ionicons
      name={icon}
      size={21}
      color={
        C.teal
      }
      />

      <Text
      style={
        styles.statValue
      }
      >
      {value}
      </Text>

      <Text
      style={
        styles.statLabel
      }
      >
      {label}
      </Text>
      </View>
    );
  }

  /* ============================================================
   *   S AMPLE ROW  *
   *   ============================================================ */

  function SampleRow({
    item,
  }: {
    item: ReturnType<
    typeof sampleMetrics
    >[number];
    key?: string;
  }) {
    const row =
    item.row || {};

    const country =
    row.country ||
    "Unknown country";

          const area =
          row.area ||
          row.region ||
          "Unknown area";

    const authority =
    row.authority ||
    "Unknown authority";

    const standard =
    row.standard ||
    "Standard unavailable";

    return (
      <View
      style={
        styles.sampleRow
      }
      >
      <View
      style={[
        styles.statusDot,
        {
          backgroundColor:
          statusColor(
            item.status,
          ),
        },
      ]}
      />

      <View
      style={{
        flex: 1,
        minWidth: 0,
      }}
      >
      <Text
      style={
        styles.sampleTitle
      }
      >
      {
        item.id
      }{" "}
      ·{" "}
      {
        item.status
      }
      </Text>

      <Text
      style={
        styles.sampleMeta
      }
      >
      {country} ·{" "}
      {area} ·{" "}
      {authority} ·{" "}
      {standard}
      </Text>
      </View>

      <View
      style={
        styles.sampleRight
      }
      >
      <Text
      style={
        styles.sampleHpi
      }
      >
      HPI{" "}
      {
        item.hpi.toFixed(
          2,
        )
      }
      </Text>

      <Text
      style={
        styles.sampleHei
      }
      >
      HEI{" "}
      {
        item.hei.toFixed(
          2,
        )
      }{" "}
      · Cd{" "}
      {
        item.cd.toFixed(
          2,
        )
      }
      </Text>
      </View>
      </View>
    );
  }

  /* ============================================================
   *   I MPORT SCREE*N
   *   ============================================================ */

  function ImportScreen({
    datasets,
    token,
    refresh,
  }: {
    datasets: Dataset[];
    token: string;
    refresh: (
      token?: string,
    ) => Promise<void>;
  }) {
    const [busy, setBusy] =
    useState(false);

    const [metadata, setMetadata] =
    useState({
      data_source: "",
      laboratory_organization: "",
      report_id: "",
      analytical_method: "",
      detection_limit: "",
    });

    const updateMetadata = (
      key: keyof typeof metadata,
      value: string,
    ) => {
      setMetadata((old) => ({
        ...old,
        [key]: value,
      }));
    };

    const metadataComplete = Boolean(
      metadata.data_source.trim() &&
      metadata.laboratory_organization.trim() &&
      metadata.report_id.trim() &&
      metadata.analytical_method.trim() &&
      metadata.detection_limit.trim()
    );

    const importFile = async (
      types: string[],
    ) => {
      if (!metadataComplete) {
        Alert.alert(
          "Complete report metadata",
          "Please fill in Data Source, Laboratory / Organization, Report ID, Analytical Method, and Detection Limit before selecting a file.",
        );
        return;
      }

      try {
        const result =
        await DocumentPicker.getDocumentAsync({
          type: types,
          copyToCacheDirectory: true,
          multiple: false,
        });

        if (
          result.canceled ||
          !result.assets?.length
        ) {
          return;
        }

        const asset = result.assets[0];

        setBusy(true);

        const formData = new FormData();

        Object.entries(metadata).forEach(
          ([key, value]) => {
            formData.append(key, String(value));
          },
        );

        if (Platform.OS === "web") {
          let file: File | null = null;

          const originalFile = (asset as any).file;

          if (
            typeof File !== "undefined" &&
            originalFile instanceof File
          ) {
            file = originalFile;
          } else {
            const response = await fetch(asset.uri);

            if (!response.ok) {
              throw new Error(
                "Unable to read the selected file.",
              );
            }

            const blob = await response.blob();

            file = new File(
              [blob],
              asset.name || "dataset.csv",
              {
                type:
                asset.mimeType ||
                blob.type ||
                "text/csv",
              },
            );
          }

          formData.append(
            "file",
            file,
            file.name,
          );
        } else {
          const response = await fetch(asset.uri);

          if (!response.ok) {
            throw new Error(
              "Unable to read the selected file.",
            );
          }

          const blob = await response.blob();

          formData.append(
            "file",
            blob as any,
            asset.name || "dataset.csv",
          );
        }

        await api(
          "/datasets/import",
          {
            method: "POST",
            body: formData,
          },
          token,
        );

        await refresh(token);

        Alert.alert(
          "Import successful",
          `${asset.name || "Dataset"} was validated and added to your workspace.`,
        );

        setMetadata({
          data_source: "",
          laboratory_organization: "",
          report_id: "",
          analytical_method: "",
          detection_limit: "",
        });
      } catch (error: any) {
        console.error(
          "Dataset import failed:",
          error,
        );

        Alert.alert(
          "Import failed",
          error?.message ||
          "Could not import the file.",
        );
      } finally {
        setBusy(false);
      }
    };

    const downloadTemplate = async (format: "csv" | "xlsx") => {
      try {
        if (Platform.OS !== "web") {
          Alert.alert(
            "Template download",
            "Template downloads are available in the web application.",
          );
          return;
        }

        if (format === "csv") {
          const csvRows = [
            TEMPLATE_HEADERS.join(","),
            TEMPLATE_SAMPLE_ROW.map((value) => {
              const text = String(value);
              return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
            }).join(","),
          ];
          const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8" });
          const url = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = url;
          link.download = "MetalSense_Water_Quality_Template.csv";
          document.body.appendChild(link);
          link.click();
          link.remove();
          URL.revokeObjectURL(url);
        } else {
          const workbook = XLSX.utils.book_new();
          const worksheet = XLSX.utils.aoa_to_sheet([
            TEMPLATE_HEADERS,
            TEMPLATE_SAMPLE_ROW,
          ]);
          XLSX.utils.book_append_sheet(workbook, worksheet, "Water Quality Template");
          const output = XLSX.write(workbook, { bookType: "xlsx", type: "array" });
          const blob = new Blob([output], {
            type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          });
          const url = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = url;
          link.download = "MetalSense_Water_Quality_Template.xlsx";
          document.body.appendChild(link);
          link.click();
          link.remove();
          URL.revokeObjectURL(url);
        }
      } catch (error: any) {
        Alert.alert(
          "Template download failed",
          error?.message || "Unable to download the template.",
        );
      }
    };

    const removeDataset =
    async (
      id: string,
    ) => {
      try {
        await api(
          `/datasets/${id}`,
          {
            method: "DELETE",
          },
          token,
        );

        await refresh(token);
      } catch (error: any) {
        Alert.alert(
          "Delete failed",
          error?.message ||
          "Could not delete dataset.",
        );
      }
    };

    return (
      <View>
      <PageIntro
      eyebrow="EVIDENCE INTAKE"
      title="Import monitoring data"
      description="Attach traceable laboratory and source metadata before importing CSV or Excel monitoring data."
      />

      <View style={styles.templatePanel}>
      <Text style={styles.panelTitle}>
      Data Template
      </Text>
      <Text style={styles.panelSubtitle}>
      Download a standardized template to prepare your water quality dataset before import.
      </Text>

      <View style={styles.templateDownloadSection}>
      <Text style={styles.templateDownloadTitle}>
      Download templates
      </Text>
      <Text style={styles.templateDownloadText}>
      Use the standardized water quality format for your dataset.
      </Text>

      <Pressable
      style={({ pressed }) => [
        styles.templateDownloadButton,
        pressed && { opacity: 0.82 },
      ]}
      onPress={() => downloadTemplate("csv")}
      >
      <View style={styles.templateDownloadIcon}>
      <Ionicons
      name="download-outline"
      size={20}
      color={C.green}
      />
      </View>
      <View style={{ flex: 1 }}>
      <Text style={styles.templateDownloadButtonTitle}>
      Download CSV Template
      </Text>
      <Text style={styles.templateDownloadButtonText}>
      Standardized .csv template
      </Text>
      </View>
      <Ionicons
      name="arrow-down-circle-outline"
      size={21}
      color={C.green}
      />
      </Pressable>

      <Pressable
      style={({ pressed }) => [
        styles.templateDownloadButton,
        pressed && { opacity: 0.82 },
      ]}
      onPress={() => downloadTemplate("xlsx")}
      >
      <View style={styles.templateDownloadIcon}>
      <Ionicons
      name="grid-outline"
      size={20}
      color={C.teal}
      />
      </View>
      <View style={{ flex: 1 }}>
      <Text style={styles.templateDownloadButtonTitle}>
      Download Excel Template
      </Text>
      <Text style={styles.templateDownloadButtonText}>
      Standardized .xlsx template
      </Text>
      </View>
      <Ionicons
      name="arrow-down-circle-outline"
      size={21}
      color={C.teal}
      />
      </Pressable>
      </View>
      </View>

      <View style={styles.panel}>
      <Text style={styles.panelTitle}>
      Report metadata
      </Text>
      <Text style={styles.panelSubtitle}>
      These fields are sent with the dataset import and should be persisted by the backend.
      </Text>

      <View style={styles.metadataGrid}>
      <Field
      label="DATA SOURCE *"
      value={metadata.data_source}
      onChangeText={(value) =>
        updateMetadata("data_source", value)
      }
      placeholder="Field survey / Laboratory"
      compact
      />
      <Field
      label="LABORATORY / ORGANIZATION *"
      value={metadata.laboratory_organization}
      onChangeText={(value) =>
        updateMetadata(
          "laboratory_organization",
          value,
        )
      }
      placeholder="Laboratory or organization name"
      compact
      />
      <Field
      label="REPORT ID *"
      value={metadata.report_id}
      onChangeText={(value) =>
        updateMetadata("report_id", value)
      }
      placeholder="Report / certificate ID"
      compact
      />
      <Field
      label="ANALYTICAL METHOD *"
      value={metadata.analytical_method}
      onChangeText={(value) =>
        updateMetadata(
          "analytical_method",
          value,
        )
      }
      placeholder="ICP-MS / AAS / other"
      compact
      />
      <Field
      label="DETECTION LIMIT *"
      value={metadata.detection_limit}
      onChangeText={(value) =>
        updateMetadata(
          "detection_limit",
          value,
        )
      }
      placeholder="e.g. 0.001 mg/L"
      compact
      />
      </View>
      </View>

      {busy && (
        <View style={styles.loadingBanner}>
        <ActivityIndicator color={C.green} />
        <Text style={styles.loadingText}>
        Importing dataset…
        </Text>
        </View>
      )}

      {!metadataComplete ? (
        <View style={styles.importLockedBanner}>
        <View style={styles.importLockedIcon}>
        <Ionicons
        name="lock-closed-outline"
        size={18}
        color={C.warning}
        />
        </View>
        <View style={{ flex: 1 }}>
        <Text style={styles.importLockedTitle}>
        File import is locked
        </Text>
        <Text style={styles.importLockedText}>
        Complete all 5 required metadata fields before selecting a CSV or Excel file.
        </Text>
        </View>
        </View>
      ) : (
        <View style={styles.importReadyBanner}>
        <View style={styles.importReadyIcon}>
        <Ionicons
        name="checkmark-circle-outline"
        size={18}
        color={C.green}
        />
        </View>
        <Text style={styles.importReadyText}>
        Required metadata complete. You can now import a file.
        </Text>
        </View>
      )}

      <View style={styles.importChoiceRow}>
      <ImportChoice
      icon="document-text-outline"
      title="IMPORT CSV"
      subtitle="Comma-separated values"
      disabled={!metadataComplete || busy}
      onPress={() =>
        importFile([
          "text/csv",
          ".csv",
        ])
      }
      />

      <ImportChoice
      icon="grid-outline"
      title="IMPORT EXCEL"
      subtitle=".xlsx or .xls workbook"
      disabled={!metadataComplete || busy}
      onPress={() =>
        importFile([
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "application/vnd.ms-excel",
          ".xlsx",
          ".xls",
        ])
      }
      />
      </View>

      <View style={styles.panel}>
      <Text style={styles.panelTitle}>
      Imported sample files
      </Text>

      <Text style={styles.panelSubtitle}>
      Persisted in your workspace
      </Text>

      {datasets.length === 0 ? (
        <EmptyState
        icon="documents-outline"
        title="No imported files"
        text="Choose CSV or Excel above."
        />
      ) : (
        datasets.map((dataset) => (
          <View
          style={styles.datasetItem}
          key={dataset.dataset_id}
          >
          <Ionicons
          name="documents-outline"
          size={23}
          color={C.teal}
          />

          <View style={{ flex: 1 }}>
          <Text style={styles.datasetName}>
          {dataset.filename}
          </Text>

          <Text style={styles.datasetMeta}>
          {dataset.records?.length || 0} records ·{" "}
          {dataset.columns?.length || 0} columns ·{" "}
          {prettyDate(dataset.imported_at)}
          </Text>

          <Text style={styles.datasetMeta}>
          {dataset.data_source || "Source not provided"} ·{" "}
          {dataset.report_id || "Report ID not provided"}
          </Text>
          </View>

          <View style={styles.datasetScore}>
          <Text style={styles.datasetScoreValue}>
          {Math.round(
            dataset.quality?.score ?? 0,
          )}
          </Text>
          <Text style={styles.datasetScoreLabel}>
          {dataset.source_type ===
            "metalsense_export"
            ? "integrity"
            : "quality"}
            </Text>
            </View>

            <Pressable
            onPress={() =>
              removeDataset(
                dataset.dataset_id,
              )
            }
            style={{ padding: 8 }}
            >
            <Ionicons
            name="trash-outline"
            size={20}
            color={C.danger}
            />
            </Pressable>
            </View>
        ))
      )}
      </View>

      <View style={styles.panel}>
      <Text style={styles.panelTitle}>
      Required fields
      </Text>

      <Text style={styles.panelSubtitle}>
      The dataset must contain these signals
      </Text>

      <Text style={styles.bullet}>
      • latitude / lat and longitude / lon / lng
      </Text>

      <Text style={styles.bullet}>
      • at least one supported metal: Pb, Cd, As, Cr, Hg, Ni, Cu, Zn, Fe, Mn
      </Text>

      <Text style={styles.bullet}>
      • optional: sample ID, date/time, water body or uploaded location fields
      </Text>
      </View>
      </View>
    );
  }

  /* ============================================================
   *   I MPORT CHOIC*E
   *   ============================================================ */

  function ImportChoice({
    icon,
    title,
    subtitle,
    onPress,
    disabled = false,
  }: {
    icon: keyof typeof Ionicons.glyphMap;
    title: string;
    subtitle: string;
    onPress: () => void;
    disabled?: boolean;
  }) {
    return (
      <Pressable
      disabled={disabled}
      onPress={disabled ? undefined : onPress}
      style={({
        pressed,
      }) => [
        styles.importChoice,
        disabled && styles.importChoiceDisabled,
        pressed && !disabled && {
          opacity: 0.75,
        },
      ]}
      >
      <View style={[
        styles.importChoiceIcon,
        disabled && styles.importChoiceIconDisabled,
      ]}>
      <Ionicons
      name={disabled ? "lock-closed-outline" : icon}
      size={27}
      color={disabled ? "#AAB8B5" : C.teal}
      />
      </View>

      <Text
      style={[
        styles.importChoiceTitle,
        disabled && styles.importChoiceTitleDisabled,
      ]}
      >
      {title}
      </Text>

      <Text
      style={[
        styles.importChoiceSubtitle,
        disabled && styles.importChoiceSubtitleDisabled,
      ]}
      >
      {subtitle}
      </Text>

      {disabled ? (
        <Text style={styles.importChoiceLockedText}>
        Complete metadata first
        </Text>
      ) : (
        <Text style={styles.browseText}>
        Browse file →
        </Text>
      )}
      </Pressable>
    );
  }

  /* ============================================================
   *   Q UALITY SCRE*EN
   *   ============================================================ */

  function QualityScreen({
    dataset,
  }: {
    dataset?: Dataset;
  }) {
    const quality =
    dataset?.quality || {};

    const isExport =
    dataset?.source_type ===
    "metalsense_export";

            const score = Math.round(
              quality.score ?? 0,
            );

            const qualityLabel =
            isExport
            ? "Export Integrity"
            : "Data Quality";

            const qualityEyebrow =
            isExport
            ? "EXPORT INTEGRITY"
            : "VALIDATION GATE";

            const qualityDescription =
            isExport
            ? "Integrity is calculated from the completeness and validity of the previously exported MetalSense results."
            : "Quality signals are calculated from the persisted import, not estimated.";

            const total =
            quality.valid_records ??
            dataset?.records?.length ??
            0;

            const valid =
            quality.valid_records ??
            total;

            const checks = getQualityChecks(
              dataset,
            );

            const issues = checks.filter(
              (check) => check.count > 0,
            ).length;

            return (
              <View>
              <PageIntro
              eyebrow={qualityEyebrow}
              title={qualityLabel}
              description={qualityDescription}
              />

              <View style={styles.qualityHero}>
              <Text style={styles.qualityEyebrow}>
              {qualityLabel.toUpperCase()} SCORE
              </Text>

              <View style={styles.qualityScoreLine}>
              <Text style={styles.qualityScore}>
              {score}
              </Text>
              <Text style={styles.qualityOutOf}>
              / 100
              </Text>
              </View>

              <Text style={styles.qualityGrade}>
              {score >= 90
                ? "Excellent"
                : score >= 75
                ? "Good"
                : score >= 50
                ? "Fair"
                : "Needs review"}
                </Text>
                </View>

                <View style={styles.statRow}>
                <StatCard
                icon="list-outline"
                value={total}
                label="Total records"
                />
                <StatCard
                icon="checkmark-circle-outline"
                value={valid}
                label="Valid records"
                />
                <StatCard
                icon="alert-circle-outline"
                value={issues}
                label="Checks needing review"
                />
                </View>

                <View style={styles.panel}>
                <Text style={styles.panelTitle}>
                Checks performed
                </Text>

                <Text style={styles.panelSubtitle}>
                Automated validation checks across the imported dataset
                </Text>

                {checks.map((check) => (
                  <View
                  key={check.label}
                  style={styles.checkRow}
                  >
                  <View
                  style={[
                    styles.checkIcon,
                    {
                      backgroundColor:
                      check.count > 0
                      ? C.mint2
                      : C.mint2,
                    },
                  ]}
                  >
                  <Ionicons
                  name={check.icon}
                  size={17}
                  color={
                    check.count > 0
                    ? C.danger
                    : C.green
                  }
                  />
                  </View>

                  <View style={{ flex: 1 }}>
                  <Text style={styles.checkTitle}>
                  {check.label}
                  </Text>
                  <Text style={styles.checkMeta}>
                  {check.count === 0
                    ? "No issues detected"
                    : `${check.count} record${
                      check.count === 1
                      ? ""
                      : "s"
                    } flagged`}
                    </Text>
                    </View>

                    <View
                    style={[
                      styles.checkBadge,
                      {
                        backgroundColor:
                        check.count > 0
                        ? C.mint2
                        : C.mint2,
                      },
                    ]}
                    >
                    <Text
                    style={[
                      styles.checkBadgeText,
                      {
                        color:
                        check.count > 0
                        ? C.danger
                        : C.green,
                      },
                    ]}
                    >
                    {check.count === 0
                      ? "PASS"
                      : "REVIEW"}
                      </Text>
                      </View>
                      </View>
                ))}
                </View>
                </View>
            );
  }

  /* ============================================================
   *   A NALYSIS    *
   *   ============================================================ */

  function AnalysisScreen({
    dataset,
    token,
  }: {
    dataset?: Dataset;
    token: string;
  }) {
    const [summary, setSummary] =
    useState<AnalysisSummary | null>(null);

    const [metals, setMetals] =
    useState<MetalAnalysis[]>([]);

    const [loading, setLoading] =
    useState(false);

    const [error, setError] =
    useState("");

    useEffect(() => {
      let active = true;

      if (!dataset?.dataset_id || !token) {
        setSummary(null);
        setMetals([]);
        return () => {
          active = false;
        };
      }

      setLoading(true);
      setError("");

      Promise.all([
        api(
          `/analysis/${dataset.dataset_id}/summary`,
          {},
          token,
        ),
        api(
          `/analysis/${dataset.dataset_id}/metals`,
          {},
          token,
        ),
      ])
      .then(([summaryData, metalData]) => {
        if (!active) return;

        setSummary(summaryData);
        setMetals(
          Array.isArray(metalData?.metals)
          ? metalData.metals
          : [],
        );
      })
      .catch((err: any) => {
        console.error(
          "Analysis API failed:",
          err,
        );
        if (active) {
          setError(
            err?.message ||
            "Unable to load backend analysis.",
          );
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

      return () => {
        active = false;
      };
    }, [dataset?.dataset_id, token]);

    const avgHpi =
    summary?.average_hpi ?? 0;
    const avgHei =
    summary?.average_hei ?? 0;
    const avgCd =
    summary?.average_cd ?? 0;
    const critical =
    summary?.high_samples ?? 0;

    const samples =
    sampleMetrics(dataset);

    const [selectedSampleId, setSelectedSampleId] =
    useState<string>(
      samples[0]?.id || "",
    );

    const [sampleDropdownOpen, setSampleDropdownOpen] =
    useState(false);

    useEffect(() => {
      if (samples.length === 0) {
        setSelectedSampleId("");
        return;
      }

      const stillExists = samples.some(
        (item) => item.id === selectedSampleId,
      );

      if (!stillExists) {
        setSelectedSampleId(samples[0].id);
      }
    }, [dataset?.dataset_id, samples.length]);

    const selectedSample =
    samples.find(
      (item) => item.id === selectedSampleId,
    ) || samples[0];

    const displayHpi =
    selectedSample?.hpi ?? avgHpi;
    const displayHei =
    selectedSample?.hei ?? avgHei;
    const displayCd =
    selectedSample?.cd ?? avgCd;

    const selectedSampleLocation = selectedSample
    ? rowLabel(
      selectedSample.row,
      [
        "location",
        "area",
        "region",
        "water_body",
      ],
    )
    : "";

    return (
      <View>
      <View style={styles.analysisHeader}>
      <View style={styles.analysisHeaderText}>
      <Text style={styles.pageEyebrow}>
      DETERMINISTIC INDICES
      </Text>

      <Text style={styles.pageTitle}>
      Pollution analysis
      </Text>

      <Text style={styles.pageDescription}>
      Select a sample to inspect its pollution indices, status, and measured metal values.
      </Text>
      </View>

      <View style={styles.sampleSelectorPanel}>
      <View style={styles.sampleSelectorHeader}>
      <View style={{ flex: 1 }}>
      <Text style={styles.sampleSelectorTitle}>
      Select sample
      </Text>
      <Text style={styles.sampleSelectorSubtitle}>
      Choose a sample for analysis
      </Text>
      </View>
      </View>

      <Pressable
      onPress={() =>
        setSampleDropdownOpen(!sampleDropdownOpen)
      }
      style={styles.sampleSelectorButton}
      disabled={samples.length === 0}
      >
      <View style={{ flex: 1 }}>
      <Text
      style={styles.sampleSelectorValue}
      numberOfLines={1}
      >
      {selectedSample
        ? selectedSample.id
        : "No samples available"}
        </Text>

        {selectedSampleLocation ? (
          <Text
          style={styles.sampleSelectorMeta}
          numberOfLines={1}
          >
          {selectedSampleLocation}
          </Text>
        ) : null}
        </View>

        <Ionicons
        name={
          sampleDropdownOpen
          ? "chevron-up-outline"
          : "chevron-down-outline"
        }
        size={18}
        color={C.teal}
        />
        </Pressable>

        {sampleDropdownOpen && samples.length > 0 && (
          <View style={styles.sampleDropdown}>
          <ScrollView
          style={styles.sampleDropdownScroll}
          nestedScrollEnabled
          >
          {samples.map((item) => {
            const active =
            item.id === selectedSample?.id;

            const location = rowLabel(
              item.row,
              [
                "location",
                "area",
                "region",
                "water_body",
              ],
            );

            return (
              <Pressable
              key={item.id}
              onPress={() => {
                setSelectedSampleId(item.id);
                setSampleDropdownOpen(false);
              }}
              style={[
                styles.sampleDropdownOption,
                active &&
                styles.sampleDropdownOptionActive,
              ]}
              >
              <View
              style={[
                styles.statusDot,
                {
                  backgroundColor: statusColor(
                    item.status,
                  ),
                },
              ]}
              />

              <View style={{ flex: 1 }}>
              <Text
              style={styles.sampleDropdownName}
              >
              {item.id}
              </Text>

              <Text
              style={styles.sampleDropdownMeta}
              numberOfLines={1}
              >
              {location || "Location not provided"}
              </Text>
              </View>

              <View style={styles.sampleDropdownMetrics}>
              <Text style={styles.sampleDropdownMetric}>
              HPI {item.hpi.toFixed(2)}
              </Text>
              <Text style={styles.sampleDropdownMetric}>
              HEI {item.hei.toFixed(2)}
              </Text>
              <Text style={styles.sampleDropdownMetric}>
              Cd {item.cd.toFixed(2)}
              </Text>
              </View>

              {active && (
                <Ionicons
                name="checkmark-circle"
                size={18}
                color={C.green}
                />
              )}
              </Pressable>
            );
          })}
          </ScrollView>
          </View>
        )}
        </View>
        </View>

        {loading && (
          <View style={styles.loadingBanner}>
          <ActivityIndicator color={C.green} />
          <Text style={styles.loadingText}>
          Loading backend analysis…
          </Text>
          </View>
        )}

        {!!error && (
          <View style={styles.loadingBanner}>
          <Ionicons
          name="alert-circle-outline"
          size={19}
          color={C.danger}
          />
          <Text
          style={[
            styles.loadingText,
            { color: C.danger },
          ]}
          >
          {error}
          </Text>
          </View>
        )}

        <View style={styles.gaugeRow}>
        <PollutionGauge
        value={displayHpi}
        label="HPI"
        max={300}
        />
        <PollutionGauge
        value={displayHei}
        label="HEI"
        max={50}
        />
        <PollutionGauge
        value={displayCd}
        label="CD"
        max={25}
        />
        </View>

        <View style={styles.singleStat}>
        <Ionicons
        name="alert-circle-outline"
        size={21}
        color={C.danger}
        />
        <Text style={styles.bigStat}>
        {critical}
        </Text>
        <Text style={styles.statLabel}>
        High-risk samples
        </Text>
        </View>

        <View style={styles.panel}>
        <Text style={styles.panelTitle}>
        Sample pollution data
        </Text>
        <Text style={styles.panelSubtitle}>
        Select a sample above to inspect its pollution indices
        </Text>

        {samples.length === 0 ? (
          <EmptyState
          icon="analytics-outline"
          title="No sample analysis available"
          text="Import a dataset and select it as the active dataset."
          />
        ) : (
          samples.map((item) => (
            <Pressable
            key={item.id}
            style={({ pressed }) => [
              styles.sampleRow,
              pressed && {
                backgroundColor: C.mint2,
              },
            ]}
            >
            <View
            style={[
              styles.statusDot,
              {
                backgroundColor:
                statusColor(
                  item.status,
                ),
              },
            ]}
            />

            <View style={{ flex: 1 }}>
            <Text style={styles.sampleTitle}>
            {item.id} · {item.status}
            </Text>
            <Text style={styles.sampleMeta}>
            {rowLabel(
              item.row,
              [
                "location",
                "area",
                "region",
                "water_body",
              ],
            ) || "Location not provided"}
            </Text>
            </View>

            <View style={styles.sampleRight}>
            <Text style={styles.sampleHpi}>
            HPI{" "}
            {item.hpi.toFixed(2)}
            </Text>
            <Text style={styles.sampleHei}>
            HEI{" "}
            {item.hei.toFixed(2)}
            {" · Cd "}
            {item.cd.toFixed(2)}
            </Text>
            </View>
            </Pressable>
          ))
        )}
        </View>

        <View style={styles.panel}>
        <Text style={styles.panelTitle}>
        Metal analysis
        </Text>

        <Text style={styles.panelSubtitle}>
        Loaded from /analysis/{'{dataset_id}'}/metals
        </Text>

        {metals.length === 0 ? (
          <EmptyState
          icon="analytics-outline"
          title="No metal analysis available"
          text="Import a dataset and select it as the active dataset."
          />
        ) : (
          metals.map((metal) => (
            <View
            key={metal.metal}
            style={styles.sampleRow}
            >
            <View
            style={[
              styles.statusDot,
              {
                backgroundColor:
                (metal.maximum_exceedance ??
                0) > 0
                ? C.high
                : C.green,
              },
            ]}
            />

            <View style={{ flex: 1 }}>
            <Text style={styles.sampleTitle}>
            {metal.metal}
            </Text>
            <Text style={styles.sampleMeta}>
            {metal.sample_count} samples · max exceedance{" "}
            {Number(
              metal.maximum_exceedance ??
              0,
            ).toFixed(2)}
            %
            </Text>
            </View>

            <View style={styles.sampleRight}>
            <Text style={styles.sampleHpi}>
            Ratio{" "}
            {Number(
              metal.average_ratio ??
              0,
            ).toFixed(3)}
            </Text>
            <Text style={styles.sampleHei}>
            Avg{" "}
            {Number(
              metal.average_measured ??
              0,
            ).toFixed(4)}{" "}
            mg/L
            </Text>
            </View>
            </View>
          ))
        )}
        </View>
        </View>
    );
  }

  /* ============================================================
   *   P O L L U T I O N   G A U G E
   *   ============================================================ */

  function polarToCartesian(
    cx: number,
    cy: number,
    radius: number,
    angleInDegrees: number,
  ) {
    const angleInRadians =
    ((angleInDegrees - 90) * Math.PI) / 180;

    return {
      x: cx + radius * Math.cos(angleInRadians),
      y: cy + radius * Math.sin(angleInRadians),
    };
  }

  function describeGaugeArc(
    cx: number,
    cy: number,
    radius: number,
    startAngle: number,
    endAngle: number,
  ) {
    const start = polarToCartesian(
      cx,
      cy,
      radius,
      endAngle,
    );
    const end = polarToCartesian(
      cx,
      cy,
      radius,
      startAngle,
    );

    const largeArcFlag =
    endAngle - startAngle <= 180 ? "0" : "1";

    return [
      "M",
      start.x,
      start.y,
      "A",
      radius,
      radius,
      0,
      largeArcFlag,
      0,
      end.x,
      end.y,
    ].join(" ");
  }

  function PollutionGauge({
    value,
    label,
    max,
  }: {
    value: number;
    label: string;
    max: number;
  }) {
    const safeValue = Number.isFinite(value)
    ? Math.max(0, value)
    : 0;

    const percentage =
    max > 0
    ? Math.min(safeValue / max, 1)
    : 0;

    // 0 = left side, 100% = right side.
    const needleAngle =
    -90 + percentage * 180;

    const needleEnd = polarToCartesian(
      90,
      88,
      58,
      needleAngle,
    );

    const status =
    percentage < 0.33
    ? "SAFE"
    : percentage < 0.66
    ? "MODERATE"
    : "CRITICAL";

    const statusColor =
    percentage < 0.33
    ? C.green
    : percentage < 0.66
    ? C.warning
    : C.danger;

    return (
      <View style={styles.gaugeCard}>
      <Svg
      width="180"
      height="132"
      viewBox="0 0 180 132"
      >
      {/* Green / safe section */}
      <Path
      d={describeGaugeArc(
        90,
        88,
        67,
        -90,
        -30,
      )}
      fill="none"
      stroke={C.teal}
      strokeWidth="13"
      />

      {/* Yellow / moderate section */}
      <Path
      d={describeGaugeArc(
        90,
        88,
        67,
        -30,
        30,
      )}
      fill="none"
      stroke={C.warning}
      strokeWidth="13"
      />

      {/* Orange section */}
      <Path
      d={describeGaugeArc(
        90,
        88,
        67,
        30,
        60,
      )}
      fill="none"
      stroke={C.high}
      strokeWidth="13"
      />

      {/* Red / critical section */}
      <Path
      d={describeGaugeArc(
        90,
        88,
        67,
        60,
        90,
      )}
      fill="none"
      stroke={C.danger}
      strokeWidth="13"
      />

      {/* Needle */}
      <Line
      x1="90"
      y1="88"
      x2={needleEnd.x}
      y2={needleEnd.y}
      stroke={C.text}
      strokeWidth="2.5"
      strokeLinecap="round"
      />

      {/* Needle center */}
      <Circle
      cx="90"
      cy="88"
      r="4"
      fill={C.text}
      />
      </Svg>

      <View style={styles.gaugeValueContainer}>
      <Text style={styles.gaugeValue}>
      {safeValue.toFixed(2)}
      </Text>

      <Text
      style={[
        styles.gaugeStatus,
        { color: statusColor },
      ]}
      >
      {status}
      </Text>

      <Text style={styles.gaugeLabel}>
      {label}
      </Text>
      </View>
      </View>
    );
  }

  async function loadGoogleMaps() {
    if (Platform.OS !== "web") {
      throw new Error("Google Maps is configured for the web app.");
    }

    if (!GOOGLE_MAPS_API_KEY) {
      throw new Error(
        "Missing EXPO_PUBLIC_GOOGLE_MAPS_API_KEY in frontend/.env.",
      );
    }

    const getGoogle = () =>
    (globalThis as any).google as any;

    const hasMaps = () => {
      const google = getGoogle();
      return Boolean(
        google?.maps?.Map &&
        google?.maps?.marker?.AdvancedMarkerElement,
      );
    };

    if (hasMaps()) {
      return getGoogle();
    }

    const existingScript = document.querySelector(
      'script[data-metalsense-google-maps="true"]',
    ) as HTMLScriptElement | null;

    if (existingScript && !hasMaps()) {
      existingScript.remove();
    }

    if (!document.querySelector(
      'script[data-metalsense-google-maps="true"]',
    )) {
      await new Promise<void>((resolve, reject) => {
        const script = document.createElement("script");

        script.dataset.metalsenseGoogleMaps = "true";

        script.src =
        `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(
          GOOGLE_MAPS_API_KEY,
        )}&v=weekly&libraries=marker`;

        script.async = true;
        script.defer = true;

        script.onload = () => {
          if (hasMaps()) {
            resolve();
          } else {
            reject(
              new Error(
                "Google Maps loaded, but the Maps/Marker libraries are unavailable.",
              ),
            );
          }
        };

        script.onerror = () =>
        reject(
          new Error(
            "Google Maps JavaScript API failed to load.",
          ),
        );

        document.head.appendChild(script);
      });
    } else {
      await new Promise<void>((resolve, reject) => {
        const started = Date.now();

        const timer = window.setInterval(() => {
          if (hasMaps()) {
            window.clearInterval(timer);
            resolve();
            return;
          }

          if (Date.now() - started > 15000) {
            window.clearInterval(timer);
            reject(
              new Error(
                "Timed out waiting for Google Maps.",
              ),
            );
          }
        }, 100);
      });
    }

    return getGoogle();
  }

  /* ============================================================
   *   S PATIAL     *
   *   ============================================================ */

  function SpatialScreen({
    dataset,
    token,
  }: {
    dataset?: Dataset;
    token: string;
  }) {
    const [mapData, setMapData] =
    useState<MapPointsResponse | null>(null);
    const [mapSummary, setMapSummary] =
    useState<MapSummary | null>(null);
    const [hotspotData, setHotspotData] =
    useState<MapHotspotsResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [mapLoading, setMapLoading] = useState(false);
    const [error, setError] = useState("");

    const mapElementRef = React.useRef<any>(null);
    const mapRef = React.useRef<any>(null);
    const markersRef = React.useRef<any[]>([]);
    const circlesRef = React.useRef<any[]>([]);

    useEffect(() => {
      let active = true;

      if (!dataset?.dataset_id || !token) {
        setMapData(null);
        setMapSummary(null);
        setHotspotData(null);
        return () => { active = false; };
      }

      setLoading(true);
      setError("");

      Promise.all([
        api(`/map/${dataset.dataset_id}/points`, {}, token),
                  api(`/map/${dataset.dataset_id}/summary`, {}, token),
                  api(`/map/${dataset.dataset_id}/hotspots?radius_km=5`, {}, token),
      ])
      .then(([points, summary, hotspots]) => {
        if (!active) return;
        setMapData(points);
        setMapSummary(summary);
        setHotspotData(hotspots);
      })
      .catch((err: any) => {
        console.error("Map API failed:", err);
        if (active) {
          setError(err?.message || "Unable to load spatial map data.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

        return () => { active = false; };
    }, [dataset?.dataset_id, token]);

    const points = mapData?.points ?? [];

    useEffect(() => {
      if (Platform.OS !== "web" || !points.length || !mapElementRef.current) {
        return;
      }

      let cancelled = false;

      const renderMap = async () => {
        try {
          setMapLoading(true);

          const google = await loadGoogleMaps();
          if (cancelled) return;

          const Map = google.maps.Map;
          const AdvancedMarkerElement =
          google.maps.marker.AdvancedMarkerElement;
          const PinElement =
          google.maps.marker.PinElement;

          if (!Map || !AdvancedMarkerElement || !PinElement) {
            throw new Error(
              "Google Maps loaded, but the required Maps/Marker classes are unavailable.",
            );
          }

          markersRef.current.forEach((marker) => { marker.map = null; });
          markersRef.current = [];
          circlesRef.current.forEach((circle) => circle.setMap(null));
          circlesRef.current = [];

          const first = points[0];
          const center = {
            lat: Number(mapSummary?.center?.latitude ?? first.latitude),
              lng: Number(mapSummary?.center?.longitude ?? first.longitude),
          };

          const map = new Map(mapElementRef.current, {
            center,
            zoom: points.length === 1 ? 14 : 7,
            mapId: "DEMO_MAP_ID",
            streetViewControl: false,
            mapTypeControl: false,
            fullscreenControl: true,
            zoomControl: true,
            clickableIcons: false,
          });

          mapRef.current = map;

          const infoWindow = new google.maps.InfoWindow();

          const bounds = new google.maps.LatLngBounds();

          points.forEach((point) => {
            const lat = Number(point.latitude);
            const lng = Number(point.longitude);
            bounds.extend({ lat, lng });

            const color = statusColor(point.status || "UNKNOWN");
            const pin = new PinElement({
              background: color,
              borderColor: color,
              glyphColor: "#FFFFFF",
            });

            const marker = new AdvancedMarkerElement({
              map,
              position: { lat, lng },
              title: `${point.sample_id} · ${point.status || "UNKNOWN"}`,
              content: pin.element,
              gmpClickable: true,
            });

            marker.addListener("click", () => {
              const hpi = point.hpi == null ? "N/A" : Number(point.hpi).toFixed(2);
              const hei = point.hei == null ? "N/A" : Number(point.hei).toFixed(2);
              const cd = point.cd == null ? "N/A" : Number(point.cd).toFixed(2);

              infoWindow.setContent(`
              <div style="min-width:230px;font-family:Arial,sans-serif;color:#405168;padding:4px">
              <div style="font-size:16px;font-weight:700;margin-bottom:5px">${point.sample_id}</div>
              <div style="font-size:12px;font-weight:700;color:${color};margin-bottom:9px">${point.status || "UNKNOWN"}</div>
              <div style="font-size:13px;line-height:1.65">
              <b>HPI:</b> ${hpi}<br/>
              <b>HEI:</b> ${hei}<br/>
              <b>Cd:</b> ${cd}<br/>
              <b>Highest metal:</b> ${point.highest_metal || "N/A"}<br/>
              <b>Water body:</b> ${point.water_body || "Not provided"}<br/>
              <b>Water type:</b> ${point.water_type || "Not provided"}<br/>
              <b>Area:</b> ${point.area || point.region || "N/A"}<br/>
              <b>Standard:</b> ${point.standard || "N/A"}
              </div>
              </div>
              `);
              infoWindow.open({ map, anchor: marker });
            });

            markersRef.current.push(marker);
          });

          if (points.length > 1) {
            map.fitBounds(bounds, 60);
          }

          (hotspotData?.hotspots ?? []).forEach((hotspot) => {
            const circle = new google.maps.Circle({
              map,
              center: {
                lat: Number(hotspot.center.latitude),
                                                  lng: Number(hotspot.center.longitude),
              },
              radius: Number(hotspot.radius_km) * 1000,
                                                  fillColor: C.danger,
                                                  fillOpacity: 0.10,
                                                  strokeColor: C.danger,
                                                  strokeOpacity: 0.45,
                                                  strokeWeight: 2,
                                                  clickable: false,
            });
            circlesRef.current.push(circle);
          });
        } catch (err: any) {
          console.error("Google Maps failed:", err);
          if (!cancelled) {
            setError(err?.message || "Unable to initialize Google Maps.");
          }
        } finally {
          if (!cancelled) setMapLoading(false);
        }
      };

      renderMap();

      return () => {
        cancelled = true;
        markersRef.current.forEach((marker) => { marker.map = null; });
        markersRef.current = [];
        circlesRef.current.forEach((circle) => circle.setMap(null));
        circlesRef.current = [];
      };
    }, [points, mapSummary, hotspotData]);

    return (
      <View>
      <PageIntro
      eyebrow="COORDINATE INTELLIGENCE"
      title="Spatial & temporal"
      description="Explore monitoring locations, risk levels, and spatial clusters directly on the Google Maps layer."
      />

      {(loading || mapLoading) && (
        <View style={styles.loadingBanner}>
        <ActivityIndicator color={C.green} />
        <Text style={styles.loadingText}>
        {loading ? "Loading map data…" : "Initializing Google Maps…"}
        </Text>
        </View>
      )}

      {!!error && (
        <View style={styles.loadingBanner}>
        <Ionicons name="alert-circle-outline" size={19} color={C.danger} />
        <Text style={[styles.loadingText, { color: C.danger }]}>
        {error}
        </Text>
        </View>
      )}

      <View style={styles.panel}>
      <Text style={styles.panelTitle}>Pollution map</Text>
      <Text style={styles.panelSubtitle}>
      {points.length} monitoring points · {mapSummary?.high_risk_count ?? 0} high-risk · {mapSummary?.moderate_count ?? 0} moderate · {mapSummary?.low_risk_count ?? 0} low
      </Text>

      {Platform.OS !== "web" ? (
        <View style={styles.mapFallback}>
        <Ionicons name="map-outline" size={42} color={C.teal} />
        <Text style={styles.mapFallbackTitle}>Google Maps web layer</Text>
        <Text style={styles.mapFallbackText}>
        The interactive Google Maps layer is configured for the web application.
        </Text>
        </View>
      ) : (
        <View ref={mapElementRef} style={styles.googleMap} />
      )}
      </View>

      <TemporalTrendAnalysis dataset={dataset} />

      <View style={styles.panel}>
      <Text style={styles.panelTitle}>Risk legend</Text>
      <View style={styles.legendRow}>
      {[
        ["LOW", C.green],
        ["MODERATE", C.warning],
        ["HIGH", C.high],
        ["CRITICAL", C.danger],
      ].map(([label, color]) => (
        <View key={label} style={styles.legendItem}>
        <View style={[styles.legendDot, { backgroundColor: color }]} />
        <Text style={styles.legendText}>{label}</Text>
        </View>
      ))}
      </View>
      </View>

      <View style={styles.panel}>
      <Text style={styles.panelTitle}>Monitoring locations</Text>
      <Text style={styles.panelSubtitle}>Click a marker for the sample details.</Text>

      {points.length === 0 ? (
        <EmptyState
        icon="map-outline"
        title="No locations detected"
        text="Import a dataset containing latitude and longitude."
        />
      ) : (
        points.map((point) => (
          <View
          style={styles.sampleRow}
          key={`${point.sample_id}-${point.latitude}-${point.longitude}`}
          >
          <View
          style={[
            styles.statusDot,
            { backgroundColor: statusColor(point.status || "UNKNOWN") },
          ]}
          />

          <View style={{ flex: 1 }}>
          <Text style={styles.sampleTitle}>
          {point.sample_id} · {point.status || "UNKNOWN"}
          </Text>
          <Text style={styles.sampleMeta}>
          {Number(point.latitude).toFixed(5)}, {Number(point.longitude).toFixed(5)} · {point.country || "Unknown country"} · {point.area || point.region || "Unknown area"}
          </Text>
          </View>

          <View style={styles.sampleRight}>
          <Text style={styles.sampleHpi}>
          HPI {Number(point.hpi ?? 0).toFixed(2)}
          </Text>
          <Text style={styles.sampleHei}>
          {point.highest_metal || "No highest metal"}
          </Text>
          </View>
          </View>
        ))
      )}
      </View>
      </View>
    );
  }

  /* ============================================================
   *   R EPORTS     *
   *   ============================================================ */

  function ReportsScreen({
    dataset,
    datasets,
    user,
  }: {
    dataset?: Dataset;
    datasets: Dataset[];
    user: User;
  }) {
    const [selectedDatasetId, setSelectedDatasetId] =
    useState<string>(dataset?.dataset_id || "");

    useEffect(() => {
      if (
        dataset?.dataset_id &&
        !datasets.some(
          (item) =>
          item.dataset_id === selectedDatasetId,
        )
      ) {
        setSelectedDatasetId(dataset.dataset_id);
      }
    }, [
      dataset?.dataset_id,
      datasets,
      selectedDatasetId,
    ]);

    const selectedDataset =
    datasets.find(
      (item) =>
      item.dataset_id === selectedDatasetId,
    ) || dataset;

    const metrics = sampleMetrics(selectedDataset);

    const lowCount = metrics.filter(
      (item) => item.status === "LOW",
    ).length;

    const moderateCount = metrics.filter(
      (item) => item.status === "MODERATE",
    ).length;

    const highCount = metrics.filter(
      (item) =>
      item.status === "HIGH" ||
      item.status === "CRITICAL",
    ).length;

    const safeCount = metrics.filter(
      (item) => item.status === "SAFE",
    ).length;

    const averageHpi = metrics.length
    ? metrics.reduce(
      (sum, item) => sum + item.hpi,
                     0,
    ) / metrics.length
    : 0;

    const averageHei = metrics.length
    ? metrics.reduce(
      (sum, item) => sum + item.hei,
                     0,
    ) / metrics.length
    : 0;

    const highestHpi = metrics.length
    ? Math.max(
      ...metrics.map((item) => item.hpi),
    )
    : 0;

    const highestHpiSample = metrics.length
    ? metrics.reduce(
      (best, item) =>
      item.hpi > best.hpi ? item : best,
      metrics[0],
    )
    : null;

    const standard =
    selectedDataset?.records?.[0]?.standard ||
    selectedDataset?.records?.[0]?.analysis?.standard ||
    "Not available";

        const metalStats = (() => {
          const totals: Record<
          string,
          {
            total: number;
            count: number;
          }
          > = {};

          (selectedDataset?.records || []).forEach(
            (row) => {
              const analysisMetals = Array.isArray(
                row?.analysis?.metals,
              )
              ? row.analysis.metals
              : [];

              /*
               * Prefer the backend's normalized analysis.metals
               * collection when available. Raw uploaded metal
               * columns are only used as a fallback. This is why
               * the old report could incorrectly show
               * "Not available" even though the analysis API
               * had Pb/Cd/etc. measurements.
               */
              if (analysisMetals.length > 0) {
                analysisMetals.forEach((entry: any) => {
                  const metal = String(
                    entry?.metal ||
                    entry?.name ||
                    entry?.symbol ||
                    "",
                  ).trim();

                  const value = Number(
                    entry?.measured ??
                    entry?.numeric_value ??
                    entry?.value ??
                    entry?.calculation_value,
                  );

                  if (!metal || !Number.isFinite(value)) {
                    return;
                  }

                  if (!totals[metal]) {
                    totals[metal] = {
                      total: 0,
                      count: 0,
                    };
                  }

                  totals[metal].total += value;
                  totals[metal].count += 1;
                });
              } else {
                metalKeysFor(row).forEach((key) => {
                  const value = Number(row[key]);

                  if (!Number.isFinite(value)) {
                    return;
                  }

                  if (!totals[key]) {
                    totals[key] = {
                      total: 0,
                      count: 0,
                    };
                  }

                  totals[key].total += value;
                  totals[key].count += 1;
                });
              }
            },
          );

          return Object.entries(totals)
          .map(([metal, value]) => ({
            metal,
            average:
            value.count > 0
            ? value.total / value.count
            : 0,
          }))
          .sort(
            (a, b) => b.average - a.average,
          );
        })();

        const leadingMetal =
        metalStats[0]?.metal || "Not available";

        const maxMetalValue =
        metalStats.length > 0
        ? Math.max(
          ...metalStats.map(
            (item) => item.average,
          ),
          1,
        )
        : 1;

        const qualityChecks = getQualityChecks(
          selectedDataset,
        );

        const activeQualityChecks =
        qualityChecks.filter(
          (check) => check.count > 0,
        ).length;

        const decisionItems = [
          {
            icon:
            "warning-outline" as keyof typeof Ionicons.glyphMap,
            title:
            highCount > 0
            ? `Prioritize ${highCount} high-risk site(s)`
            : "No high-risk sites detected",
            text:
            highCount > 0
            ? "High-risk samples exceed the configured analysis thresholds. Recommend immediate re-sampling and source investigation."
            : "No high-risk samples are currently flagged by the analysis.",
            color:
            highCount > 0
            ? C.danger
            : C.green,
          },
          {
            icon:
            "flask-outline" as keyof typeof Ionicons.glyphMap,
            title:
            leadingMetal === "Not available"
            ? "No leading contaminant available"
            : `${leadingMetal} is the leading contaminant dataset-wide`,
            text:
            leadingMetal === "Not available"
            ? "No supported metal measurements are available for this dataset."
            : `${leadingMetal} has the highest aggregate measured concentration across the available sample rows. Consider targeted source tracing.`,
            color: C.warning,
          },
          {
            icon:
            "shield-checkmark-outline" as keyof typeof Ionicons.glyphMap,
            title:
            activeQualityChecks > 0
            ? `Improve data quality at ${activeQualityChecks} check(s)`
            : "Data quality checks passed",
            text:
            activeQualityChecks > 0
            ? "Review flagged validation checks before relying on computed indices for decisions."
            : "No active data-quality issues are currently reported for this dataset.",
            color: C.teal,
          },
        ];

        const exportCsv = () => {
          if (!selectedDataset) {
            Alert.alert(
              "Nothing to export",
              "Import a dataset first.",
            );
            return;
          }

          const columns =
          selectedDataset.columns ||
          Object.keys(
            selectedDataset.records?.[0] || {},
          );

          const reportColumns = [
            ...columns,
            "analysis_status",
            "analysis_hpi",
            "analysis_hei",
            "analysis_cd",
          ];

          const lines: any[][] = [
            [
              "MetalSense report",
              "",
              "",
            ],
            [
              "Dataset",
              selectedDataset.filename,
              "",
            ],
            [
              "User",
              user.full_name,
              "",
            ],
            [
              "Role",
              user.role,
              "",
            ],
            [
              "Organization",
              user.organization || "",
              "",
            ],
            [
              "Data Source",
              selectedDataset.data_source || "",
              "",
            ],
            [
              "Laboratory / Organization",
              selectedDataset.laboratory_organization || "",
              "",
            ],
            [
              "Report ID",
              selectedDataset.report_id || "",
              "",
            ],
            [
              "Analytical Method",
              selectedDataset.analytical_method || "",
              "",
            ],
            [
              "Detection Limit",
              selectedDataset.detection_limit || "",
              "",
            ],
            [],
            reportColumns,
          ];

          (selectedDataset.records || []).forEach(
            (row) => {
              const analysis = row.analysis || {};

              lines.push(
                reportColumns.map(
                  (column) => {
                    if (
                      column ===
                      "analysis_status"
                    ) {
                      return (
                        analysis.status || ""
                      );
                    }

                    if (
                      column ===
                      "analysis_hpi"
                    ) {
                      return (
                        analysis.hpi ?? ""
                      );
                    }

                    if (
                      column ===
                      "analysis_hei"
                    ) {
                      return (
                        analysis.hei ?? ""
                      );
                    }

                    if (
                      column ===
                      "analysis_cd"
                    ) {
                      return (
                        analysis.cd ?? ""
                      );
                    }

                    return String(
                      row[column] ?? "",
                    );
                  },
                ),
              );
            },
          );

          const csv = lines
          .map(
            (line: any[]) =>
            line
            .map(
              (value) =>
              `"${String(
                value ?? "",
              ).replace(
                /"/g,
                '""',
              )}"`,
            )
            .join(","),
          )
          .join("\n");

          if (Platform.OS === "web") {
            const blob = new Blob(
              [csv],
              {
                type:
                "text/csv;charset=utf-8",
              },
            );

            const url =
            URL.createObjectURL(blob);

            const anchor =
            document.createElement("a");

            anchor.href = url;

            anchor.download =
            `${selectedDataset.filename.replace(
              /\.[^.]+$/,
              "",
            )}_metalsense_report.csv`;

            anchor.click();

            URL.revokeObjectURL(url);
          } else {
            Alert.alert(
              "CSV ready",
              "CSV export is available in the web preview.",
            );
          }
        };

        const exportPdfSummary = () => {
          if (
            Platform.OS !== "web" ||
            typeof window === "undefined" ||
            typeof document === "undefined"
          ) {
            Alert.alert(
              "PDF summary",
              "PDF export is available from the web preview.",
            );
            return;
          }

          const escapeHtml = (value: any) =>
          String(value ?? "")
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#39;");

          const riskColor = (status: string) => {
            const normalized =
            String(status || "").toUpperCase();

            if (
              normalized === "HIGH" ||
              normalized === "CRITICAL"
            ) {
              return "#C94D4D";
            }

            if (normalized === "MODERATE") {
              return "#D6A329";
            }

            return "#249E73";
          };

          /*
           * IMPORTANT:
           * Chrome's print renderer can drop CSS/SVG bar fills in
           * a generated print document. We therefore render every
           * graph onto a canvas first and embed the resulting PNG.
           * A PNG is treated as a normal document image by the
           * browser print engine and prints reliably.
           */

          const canvasToDataUrl = (
            draw: (
              ctx: CanvasRenderingContext2D,
              width: number,
              height: number,
            ) => void,
            width: number,
            height: number,
          ) => {
            const canvas =
            document.createElement("canvas");

            const scale =
            Math.max(
              2,
              Math.min(
                3,
                window.devicePixelRatio || 1,
              ),
            );

            canvas.width =
            width * scale;

            canvas.height =
            height * scale;

            const ctx =
            canvas.getContext("2d");

            if (!ctx) {
              return "";
            }

            ctx.scale(
              scale,
              scale,
            );

            ctx.fillStyle =
            "#FFFFFF";

            ctx.fillRect(
              0,
              0,
              width,
              height,
            );

            draw(
              ctx,
              width,
              height,
            );

            return canvas.toDataURL(
              "image/png",
            );
          };

          /*
           * ======================================================
           * RISK DISTRIBUTION GRAPH
           * ======================================================
           */

          const riskRows = [
            [
              "LOW",
              lowCount,
              "#249E73",
            ],
            [
              "MODERATE",
              moderateCount,
              "#D6A329",
            ],
            [
              "HIGH / CRITICAL",
              highCount,
              "#C94D4D",
            ],
            [
              "SAFE",
              safeCount,
              "#188E68",
            ],
          ];

          const maxRisk = Math.max(
            lowCount,
            moderateCount,
            highCount,
            safeCount,
            1,
          );

          const riskGraph =
          canvasToDataUrl(
            (
              ctx,
             width,
             height,
            ) => {
              ctx.font =
              "700 24px Arial";

              ctx.textBaseline =
              "middle";

              riskRows.forEach(
                (
                  row,
                 index,
                ) => {
                  const label =
                  String(
                    row[0],
                  );

                  const count =
                  Number(
                    row[1],
                  );

                  const color =
                  String(
                    row[2],
                  );

                  const y =
                  38 +
                  index * 62;

                  const trackX =
                  190;

                  const trackWidth =
                  width -
                  250;

                  const barWidth =
                  Math.max(
                    12,
                    (count /
                    maxRisk) *
                    trackWidth,
                  );

                  ctx.fillStyle =
                  "#405168";

              ctx.fillText(
                label,
                12,
                y,
              );

              ctx.fillStyle =
              "#E9F2EF";

              ctx.beginPath();

              ctx.roundRect(
                trackX,
                y -
                14,
                trackWidth,
                28,
                14,
              );

              ctx.fill();

              ctx.fillStyle =
              color;

              ctx.beginPath();

              ctx.roundRect(
                trackX,
                y -
                14,
                barWidth,
                28,
                14,
              );

              ctx.fill();

              ctx.fillStyle =
              "#405168";

              ctx.textAlign =
              "right";

              ctx.fillText(
                String(
                  count,
                ),
                width - 12,
                y,
              );

              ctx.textAlign =
              "left";
                },
              );
            },
            900,
            280,
          );

          /*
           * ======================================================
           * HPI BY SAMPLE GRAPH
           * ======================================================
           */

          const maxHpi =
          Math.max(
            ...metrics.map(
              (item) =>
              item.hpi,
            ),
            1,
          );

          const hpiGraph =
          canvasToDataUrl(
            (
              ctx,
             width,
             height,
            ) => {
              const left =
              60;

              const right =
              width - 30;

              const top =
              30;

              const bottom =
              height - 55;

              const plotHeight =
              bottom - top;

              const count =
              Math.max(
                metrics.length,
                1,
              );

              const slot =
              (right -
              left) /
              count;

              ctx.strokeStyle =
              "#D4ECE5";

              ctx.lineWidth = 2;

              for (
                let i = 0;
              i <= 4;
              i += 1
              ) {
                const y =
                bottom -
                (i / 4) *
                plotHeight;

                ctx.beginPath();

                ctx.moveTo(
                  left,
                  y,
                );

                ctx.lineTo(
                  right,
                  y,
                );

                ctx.stroke();

                ctx.fillStyle =
                "#7A8989";

              ctx.font =
              "12px Arial";

                ctx.textAlign =
                "right";

              ctx.fillText(
                (
                  (maxHpi * i) /
                  4
                ).toFixed(
                  0,
                ),
                left - 8,
                y,
              );
              }

              metrics.forEach(
                (
                  item,
                 index,
                ) => {
                  const barWidth =
                  Math.min(
                    56,
                    slot * 0.48,
                  );

                  const barHeight =
                  Math.max(
                    10,
                    (item.hpi /
                    maxHpi) *
                    plotHeight,
                  );

                  const x =
                  left +
                  index *
                  slot +
                  (slot -
                  barWidth) /
                  2;

                  const y =
                  bottom -
                  barHeight;

                  ctx.fillStyle =
                  riskColor(
                    item.status,
                  );

                  ctx.beginPath();

                  ctx.roundRect(
                    x,
                    y,
                    barWidth,
                    barHeight,
                    7,
                  );

                  ctx.fill();

                  ctx.fillStyle =
                  "#405168";

                ctx.font =
                "700 12px Arial";

                  ctx.textAlign =
                  "center";

                ctx.fillText(
                  item.hpi.toFixed(
                    1,
                  ),
                  x +
                  barWidth /
                  2,
                  Math.max(
                    16,
                    y - 8,
                  ),
                );

                ctx.fillStyle =
                "#405168";

                ctx.font =
                "700 12px Arial";

                ctx.fillText(
                  String(
                    item.id,
                  ),
                  x +
                  barWidth /
                  2,
                  bottom + 25,
                );
                },
              );

              ctx.textAlign =
              "left";
            },
            1000,
            420,
          );

          /*
           * ======================================================
           * METAL CONCENTRATION GRAPH
           * ======================================================
           */

          const maxMetal =
          Math.max(
            maxMetalValue,
            0.000001,
          );

          const metalGraph =
          canvasToDataUrl(
            (
              ctx,
             width,
             height,
            ) => {
              const left =
              130;

              const right =
              width - 90;

              const top =
              30;

              const rowHeight =
              52;

              ctx.font =
              "700 18px Arial";

              ctx.textBaseline =
              "middle";

              metalStats.forEach(
                (
                  item,
                 index,
                ) => {
                  const y =
                  top +
                  index *
                  rowHeight;

                  const trackWidth =
                  right - left;

                  const barWidth =
                  Math.max(
                    10,
                    (item.average /
                    maxMetal) *
                    trackWidth,
                  );

                  ctx.fillStyle =
                  "#405168";

              ctx.fillText(
                item.metal,
                12,
                y + 11,
              );

              ctx.fillStyle =
              "#E9F2EF";

              ctx.beginPath();

              ctx.roundRect(
                left,
                y,
                trackWidth,
                22,
                11,
              );

              ctx.fill();

              ctx.fillStyle =
              "#0C92A3";

              ctx.beginPath();

              ctx.roundRect(
                left,
                y,
                barWidth,
                22,
                11,
              );

              ctx.fill();

              ctx.fillStyle =
              "#405168";

              ctx.textAlign =
              "right";

              ctx.fillText(
                item.average.toFixed(
                  4,
                ),
                width - 12,
                y + 11,
              );

              ctx.textAlign =
              "left";
                },
              );
            },
            1000,
            Math.max(
              130,
              metalStats.length *
              52 +
              40,
            ),
          );

          const tableHtml =
          metrics
          .map(
            (item) => `
            <tr>
            <td>${escapeHtml(
              item.id,
            )}</td>
            <td>${escapeHtml(
              item.row?.date,
            )}</td>
            <td>${item.lat.toFixed(
              4,
            )}</td>
            <td>${item.lon.toFixed(
              4,
            )}</td>
            <td>${item.hpi.toFixed(
              2,
            )}</td>
            <td>${item.hei.toFixed(
              2,
            )}</td>
            <td>${item.cd.toFixed(
              2,
            )}</td>
            <td
            style="
            font-weight:800;
            color:${riskColor(
              item.status,
            )}
            "
            >
            ${escapeHtml(
              item.status,
            )}
            </td>
            </tr>
            `,
          )
          .join("");

          const decisionHtml =
          decisionItems
          .map(
            (item) => `
            <div class="decision">
            <h3>
            ${escapeHtml(
              item.title,
            )}
            </h3>

            <p>
            ${escapeHtml(
              item.text,
            )}
            </p>
            </div>
            `,
          )
          .join("");

          const popup =
          window.open(
            "",
            "_blank",
            "width=1200,height=900",
          );

          if (!popup) {
            Alert.alert(
              "PDF export blocked",
              "Allow pop-ups for localhost and try again.",
            );
            return;
          }

          const reportTitle =
          `MetalSense Report - ${selectedDataset.filename}`;

          const metalGraphHtml =
          metalStats.length > 0
          ? `<img
          class="graph"
          src="${metalGraph}"
          alt="Metal concentration chart"
          />`
          : `<p>
          No supported metal measurements are available.
          </p>`;

          popup.document.open();

          popup.document.write(`
          <!doctype html>

          <html>

          <head>

          <meta charset="utf-8" />

          <title>
          ${escapeHtml(
            reportTitle,
          )}
          </title>

          <style>
          @page {
            size: A4;
            margin: 12mm;
          }

          * {
            box-sizing: border-box;
          }

          html,
          body {
            margin: 0;
            padding: 0;
            background: #ffffff;
          }

          body {
            font-family:
            Arial,
            Helvetica,
            sans-serif;

            color: #405168;

            -webkit-print-color-adjust:
            exact;

            print-color-adjust:
            exact;
          }

          h1 {
            margin:
            0
            0
            6px;

            font-size: 27px;

            color: #405168;
          }

          h2 {
            margin:
            22px
            0
            8px;

            font-size: 19px;

            color: #405168;
          }

          h3 {
            margin:
            0
            0
            5px;

            font-size: 13px;

            color: #405168;
          }

          p {
            margin: 0;

            font-size: 10px;

            line-height: 1.5;

            color: #6D7C80;
          }

          .header {
            padding-bottom: 10px;

            border-bottom:
            2px solid
            #D4ECE5;
          }

          .eyebrow {
            margin-bottom: 5px;

            color: #0C92A3;

            font-weight: 800;

            font-size: 9px;

            letter-spacing: 2px;
          }

          .meta {
            display: grid;

            grid-template-columns:
            1fr
            1fr;

            gap:
            4px
            20px;

            margin-top: 8px;

            font-size: 9px;

            color: #6D7C80;
          }

          .cards {
            display: grid;

            grid-template-columns:
            repeat(
              3,
              1fr
            );

            gap: 8px;

            margin-top: 10px;
          }

          .card {
            padding: 9px;

            border:
            1px solid
            #D4ECE5;

            border-radius: 8px;
          }

          .label {
            color: #8A9999;

            font-size: 8px;

            font-weight: 800;

            letter-spacing: 1px;
          }

          .value {
            margin-top: 4px;

            color: #405168;

            font-size: 17px;

            font-weight: 800;
          }

          .decision {
            padding: 10px;

            margin-top: 7px;

            border:
            1px solid
            #D4ECE5;

            border-radius: 8px;

            page-break-inside:
            avoid;
          }

          .graph {
            width: 100%;

            height: auto;

            display: block;

            margin-top: 5px;

            /*
             * Image rather than div/SVG:
             * this is what makes Chrome's PDF
             * printer preserve the graph.
             */
            image-rendering:
            auto;
          }

          .graph-section {
            page-break-inside:
            avoid;

            break-inside:
            avoid;
          }

          .page-break {
            page-break-before:
            always;

            break-before:
            page;
          }

          table {
            width: 100%;

            border-collapse:
            collapse;

            margin-top: 8px;

            font-size: 8px;
          }

          th {
            padding: 6px;

            text-align: left;

            background:
            #E8FAF6;

            border-bottom:
            1px solid
            #D4ECE5;
          }

          td {
            padding: 6px;

            border-bottom:
            1px solid
            #E6EFEC;
          }

          .footer {
            margin-top: 18px;

            padding-top: 8px;

            border-top:
            1px solid
            #D4ECE5;

            color: #9AA8AA;

            font-size: 8px;
          }

          @media print {
            img {
              -webkit-print-color-adjust:
              exact;

              print-color-adjust:
              exact;
            }
          }
          </style>

          </head>

          <body>

          <div class="header">

          <div class="eyebrow">
          METALSENSE · EVIDENCE-READY REPORT
          </div>

          <h1>
          Reports &amp; Decisions
          </h1>

          <p>
          Dataset:
          <strong>
          ${escapeHtml(
            selectedDataset.filename,
          )}
          </strong>
          </p>

          <div class="meta">

          <div>
          Data source:
          ${escapeHtml(
            selectedDataset.data_source ||
            "Not provided",
          )}
          </div>

          <div>
          Laboratory / organization:
          ${escapeHtml(
            selectedDataset
            .laboratory_organization ||
            "Not provided",
          )}
          </div>

          <div>
          Report ID:
          ${escapeHtml(
            selectedDataset.report_id ||
            "Not provided",
          )}
          </div>

          <div>
          Analytical method:
          ${escapeHtml(
            selectedDataset.analytical_method ||
            "Not provided",
          )}
          </div>

          <div>
          Detection limit:
          ${escapeHtml(
            selectedDataset.detection_limit ||
            "Not provided",
          )}
          </div>

          <div>
          Standard:
          ${escapeHtml(
            standard,
          )}
          </div>

          </div>

          </div>


          <h2>
          Report overview
          </h2>

          <div class="cards">

          <div class="card">
          <div class="label">
          AVERAGE HPI
          </div>

          <div class="value">
          ${averageHpi.toFixed(
            2,
          )}
          </div>
          </div>

          <div class="card">
          <div class="label">
          AVERAGE HEI
          </div>

          <div class="value">
          ${averageHei.toFixed(
            2,
          )}
          </div>
          </div>

          <div class="card">
          <div class="label">
          HIGH-RISK SAMPLES
          </div>

          <div class="value">
          ${highCount}
          </div>
          </div>

          <div class="card">
          <div class="label">
          LEADING METAL
          </div>

          <div class="value">
          ${escapeHtml(
            leadingMetal,
          )}
          </div>
          </div>

          <div class="card">
          <div class="label">
          QUALITY SCORE
          </div>

          <div class="value">
          ${Math.round(
            selectedDataset
            .quality
            ?.score ??
            0,
          )}
          </div>
          </div>

          <div class="card">
          <div class="label">
          RECORDS
          </div>

          <div class="value">
          ${
            selectedDataset
            .records
            ?.length ??
            0
          }
          </div>
          </div>

          </div>


          <h2>
          Discussion &amp; decision support
          </h2>

          ${decisionHtml}


          <div class="graph-section">

          <h2>
          Risk distribution
          </h2>

          <img
          class="graph"
          src="${riskGraph}"
          alt="Risk distribution chart"
          />

          </div>


          <div class="graph-section">

          <h2>
          HPI by sample
          </h2>

          <img
          class="graph"
          src="${hpiGraph}"
          alt="HPI by sample chart"
          />

          </div>


          <div class="page-break"></div>


          <div class="graph-section">

          <h2>
          Metal concentration profile
          </h2>

          ${metalGraphHtml}

          </div>


          <h2>
          Full results table
          </h2>

          <table>

          <thead>

          <tr>
          <th>ID</th>
          <th>Date</th>
          <th>Latitude</th>
          <th>Longitude</th>
          <th>HPI</th>
          <th>HEI</th>
          <th>Cd</th>
          <th>Status</th>
          </tr>

          </thead>

          <tbody>

          ${tableHtml}

          </tbody>

          </table>


          <div class="footer">
          Generated by MetalSense ·
          The report presents persisted
          dataset values and calculated
          analysis results.
          </div>

          </body>

          </html>
          `);

          popup.document.close();

          /*
           * Wait until the PNG images are fully decoded,
           * then trigger print. This avoids the situation where
           * Chrome captures the page before the graph images
           * have painted.
           */

          const printWhenReady =
          async () => {
            try {
              const images =
              Array.from(
                popup.document.images,
              );

              await Promise.all(
                images.map(
                  (image) => {
                    if (
                      image.complete
                    ) {
                      return Promise.resolve();
                    }

                    return new Promise<void>(
                      (resolve) => {
                        image.onload =
                        () =>
                        resolve();

                        image.onerror =
                        () =>
                        resolve();
                      },
                    );
                  },
                ),
              );
            } finally {
              window.setTimeout(
                () => {
                  try {
                    popup.focus();
                    popup.print();
                  } catch {
                    // Browser may already have opened the print dialog.
                  }
                },
                150,
              );
            }
          };

          if (
            popup.document.readyState ===
            "complete"
          ) {
            void printWhenReady();
          } else {
            popup.onload =
            () => {
              void printWhenReady();
            };
          }

          /*
           * Fallback for Chromium popup lifecycle.
           */
          window.setTimeout(
            () => {
              try {
                if (
                  popup &&
                  !popup.closed
                ) {
                  popup.focus();
                  popup.print();
                }
              } catch {
                // Ignore duplicate print lifecycle errors.
              }
            },
            1600,
          );
        };

        return (
          <View>
          <PageIntro
          eyebrow="EVIDENCE-READY OUTPUT"
          title="Reports & decisions"
          description="Select a dataset and review its decision support, pollution profile, trends, and verified sample results."
          />

          {/* ====================================================
            DATASET SELECTION
            ==================================================== */}

            <View style={styles.panel}>
            <Text style={styles.panelTitle}>
            Report dataset
            </Text>

            <Text style={styles.panelSubtitle}>
            Choose which imported file this report should analyze.
            </Text>

            <View style={styles.reportDatasetList}>
            {datasets.length === 0 ? (
              <EmptyState
              icon="documents-outline"
              title="No datasets available"
              text="Import a CSV or Excel file first."
              />
            ) : (
              datasets.map((item) => {
                const active =
                item.dataset_id ===
                selectedDatasetId;

                return (
                  <Pressable
                  key={item.dataset_id}
                  onPress={() =>
                    setSelectedDatasetId(
                      item.dataset_id,
                    )
                  }
                  style={[
                    styles.reportDatasetOption,
                    active &&
                    styles.reportDatasetOptionActive,
                  ]}
                  >
                  <View
                  style={
                    styles.reportDatasetIcon
                  }
                  >
                  <Ionicons
                  name="document-text-outline"
                  size={19}
                  color={
                    active
                    ? C.green
                    : C.teal
                  }
                  />
                  </View>

                  <View
                  style={{
                    flex: 1,
                  }}
                  >
                  <Text
                  style={
                    styles.reportDatasetName
                  }
                  >
                  {item.filename}
                  </Text>

                  <Text
                  style={
                    styles.reportDatasetMeta
                  }
                  >
                  {item.records?.length ||
                    0}{" "}
                    records ·{" "}
                    {item.columns?.length ||
                      0}{" "}
                      columns ·{" "}
                      {prettyDate(
                        item.imported_at,
                      )}
                      </Text>

                      <Text
                      style={
                        styles.reportDatasetMeta
                      }
                      >
                      {item.data_source ||
                        "Source not provided"}{" "}
                        ·{" "}
                        {item.report_id ||
                          "Report ID not provided"}
                          </Text>
                          </View>

                          <View
                          style={[
                            styles.reportDatasetRadio,
                            active &&
                            styles.reportDatasetRadioActive,
                          ]}
                          >
                          {active && (
                            <View
                            style={
                              styles.reportDatasetRadioInner
                            }
                            />
                          )}
                          </View>
                          </Pressable>
                );
              })
            )}
            </View>
            </View>

            {!selectedDataset ? (
              <EmptyState
              icon="analytics-outline"
              title="No report data"
              text="Select or import a dataset."
              />
            ) : (
              <>
              {/* ==================================================
                REPORT OVERVIEW
                ================================================== */}

                <View style={styles.panel}>
                <View
                style={
                  styles.reportHeadingRow
                }
                >
                <View
                style={{
                  flex: 1,
                }}
                >
                <Text
                style={
                  styles.panelTitle
                }
                >
                Report overview
                </Text>

                <Text
                style={
                  styles.panelSubtitle
                }
                >
                {
                  selectedDataset.filename
                }{" "}
                ·{" "}
                {metrics.length}{" "}
                samples
                </Text>
                </View>

                <View
                style={
                  styles.reportStatusPill
                }
                >
                <Text
                style={
                  styles.reportStatusPillText
                }
                >
                {highCount > 0
                  ? "REVIEW REQUIRED"
                  : "WITHIN CURRENT THRESHOLDS"}
                  </Text>
                  </View>
                  </View>

                  <View
                  style={
                    styles.reportGrid
                  }
                  >
                  <ReportCell
                  label="AVERAGE HPI"
                  value={averageHpi.toFixed(2)}
                  />

                  <ReportCell
                  label="AVERAGE HEI"
                  value={averageHei.toFixed(2)}
                  />

                  <ReportCell
                  label="HIGH-RISK SAMPLES"
                  value={String(highCount)}
                  />

                  <ReportCell
                  label="LEADING METAL"
                  value={leadingMetal}
                  />

                  <ReportCell
                  label="QUALITY SCORE"
                  value={String(
                    Math.round(
                      selectedDataset.quality?.score ?? 0,
                    ),
                  )}
                  />

                  <ReportCell
                  label="RECORDS"
                  value={String(
                    selectedDataset.records?.length ?? 0,
                  )}
                  />
                  </View>
                  </View>

                  {/* ==================================================
                    DISCUSSION & DECISION
                    ================================================== */}

                    <View style={styles.panel}>
                    <Text
                    style={styles.panelTitle}
                    >
                    Discussion & decision
                    support
                    </Text>

                    <Text
                    style={styles.panelSubtitle}
                    >
                    Interpret the calculated
                    results before taking action.
                    </Text>

                    {decisionItems.map((item) => (
                      <View
                      key={item.title}
                      style={styles.decisionCard}
                      >
                      <View
                      style={[
                        styles.decisionIcon,
                        {
                          backgroundColor: C.mint2,
                        },
                      ]}
                      >
                      <Ionicons
                      name={item.icon}
                      size={20}
                      color={item.color}
                      />
                      </View>

                      <View
                      style={{
                        flex: 1,
                      }}
                      >
                      <Text
                      style={
                        styles.decisionTitle
                      }
                      >
                      {item.title}
                      </Text>

                      <Text
                      style={
                        styles.decisionText
                      }
                      >
                      {item.text}
                      </Text>
                      </View>
                      </View>
                    ))}

                    {highestHpiSample && (
                      <View
                      style={
                        styles.reportInsight
                      }
                      >
                      <Text
                      style={
                        styles.reportInsightLabel
                      }
                      >
                      HIGHEST OBSERVED HPI
                      </Text>

                      <Text
                      style={
                        styles.reportInsightTitle
                      }
                      >
                      {highestHpiSample.id} ·{" "}
                      {highestHpiSample.status}
                      </Text>

                      <Text
                      style={
                        styles.reportInsightText
                      }
                      >
                      HPI{" "}
                      {highestHpiSample.hpi.toFixed(
                        2,
                      )}{" "}
                      · HEI{" "}
                      {highestHpiSample.hei.toFixed(
                        2,
                      )}{" "}
                      ·{" "}
                      {highestHpiSample.row?.area ||
                        highestHpiSample.row?.region ||
                        "Location not provided"}
                        .
                        </Text>
                        </View>
                    )}
                    </View>

                    {/* ==================================================
                      RISK DISTRIBUTION GRAPH
                      ================================================== */}

                      <View style={styles.panel}>
                      <Text
                      style={styles.panelTitle}
                      >
                      Risk distribution
                      </Text>

                      <Text
                      style={styles.panelSubtitle}
                      >
                      Samples grouped by their
                      calculated pollution status.
                      </Text>

                      {[
                        [
                          "LOW",
                          lowCount,
                          C.green,
                        ],
                        [
                          "MODERATE",
                          moderateCount,
                          C.warning,
                        ],
                        [
                          "HIGH / CRITICAL",
                          highCount,
                          C.danger,
                        ],
                        [
                          "SAFE",
                          safeCount,
                          C.greenDark,
                        ],
                      ].map((item) => {
                        const count =
                        Number(item[1]);

                        const maximum =
                        Math.max(
                          lowCount,
                          moderateCount,
                          highCount,
                          safeCount,
                          1,
                        );

                        return (
                          <View
                          key={String(item[0])}
                          style={styles.chartRow}
                          >
                          <Text
                          style={
                            styles.chartLabel
                          }
                          >
                          {String(item[0])}
                          </Text>

                          <View
                          style={
                            styles.chartTrack
                          }
                          >
                          <View
                          style={[
                            styles.chartBar,
                            {
                              width:
                              `${Math.max(
                                4,
                                (count /
                                maximum) *
                                100,
                              )}%`,
                              backgroundColor:
                              String(item[2]),
                            },
                          ]}
                          />
                          </View>

                          <Text
                          style={
                            styles.chartValue
                          }
                          >
                          {count}
                          </Text>
                          </View>
                        );
                      })}
                      </View>

                      {/* ==================================================
                        HPI GRAPH
                        ================================================== */}

                        <View style={styles.panel}>
                        <Text
                        style={styles.panelTitle}
                        >
                        HPI by sample
                        </Text>

                        <Text
                        style={styles.panelSubtitle}
                        >
                        Higher bars indicate greater
                        heavy-metal pollution pressure.
                        </Text>

                        {metrics.length === 0 ? (
                          <EmptyState
                          icon="bar-chart-outline"
                          title="No HPI values"
                          text="No calculated samples are available."
                          />
                        ) : (
                          <ScrollView
                          horizontal
                          showsHorizontalScrollIndicator={
                            false
                          }
                          contentContainerStyle={
                            styles.barChart
                          }
                          >
                          {metrics.map((item) => {
                            const height =
                            Math.max(
                              14,
                              (item.hpi /
                              Math.max(
                                highestHpi,
                                1,
                              )) *
                              180,
                            );

                            return (
                              <View
                              key={item.id}
                              style={
                                styles.barColumn
                              }
                              >
                              <Text
                              style={
                                styles.barValue
                              }
                              >
                              {item.hpi.toFixed(0)}
                              </Text>

                              <View
                              style={
                                styles.barArea
                              }
                              >
                              <View
                              style={[
                                styles.verticalBar,
                                {
                                  height,
                                  backgroundColor:
                                  statusColor(
                                    item.status,
                                  ),
                                },
                              ]}
                              />
                              </View>

                              <Text
                              style={
                                styles.barLabel
                              }
                              >
                              {item.id}
                              </Text>
                              </View>
                            );
                          })}
                          </ScrollView>
                        )}
                        </View>

                        {/* ==================================================
                          METAL GRAPH
                          ================================================== */}

                          <View style={styles.panel}>
                          <Text
                          style={styles.panelTitle}
                          >
                          Metal concentration profile
                          </Text>

                          <Text
                          style={styles.panelSubtitle}
                          >
                          Average measured concentration
                          across supported metals.
                          </Text>

                          {metalStats.length === 0 ? (
                            <EmptyState
                            icon="flask-outline"
                            title="No metal measurements"
                            text="No supported numeric metal values are available."
                            />
                          ) : (
                            metalStats.map((item) => (
                              <View
                              key={item.metal}
                              style={styles.chartRow}
                              >
                              <Text
                              style={
                                styles.chartLabel
                              }
                              >
                              {item.metal}
                              </Text>

                              <View
                              style={
                                styles.chartTrack
                              }
                              >
                              <View
                              style={[
                                styles.chartBar,
                                {
                                  width:
                                  `${Math.max(
                                    4,
                                    (item.average /
                                    maxMetalValue) *
                                    100,
                                  )}%`,
                                  backgroundColor:
                                  C.teal,
                                },
                              ]}
                              />
                              </View>

                              <Text
                              style={
                                styles.chartValue
                              }
                              >
                              {item.average.toFixed(3)}
                              </Text>
                              </View>
                            ))
                          )}
                          </View>

                          {/* ==================================================
                            FULL RESULTS TABLE
                            ================================================== */}

                            <View
                            style={
                              styles.sectionHeadingRow
                            }
                            >
                            <Text
                            style={
                              styles.sectionHeading
                            }
                            >
                            FULL RESULTS TABLE
                            </Text>
                            </View>

                            <View style={styles.panel}>
                            <ScrollView
                            horizontal
                            showsHorizontalScrollIndicator
                            >
                            <View
                            style={
                              styles.resultsTable
                            }
                            >
                            <View
                            style={[
                              styles.resultTableRow,
                              styles.resultTableHeader,
                            ]}
                            >
                            {[
                              "ID",
                              "DATE",
                              "LATITUDE",
                              "LONGITUDE",
                              "HPI",
                              "HEI",
                              "Cd",
                              "STATUS",
                            ].map((label) => (
                              <Text
                              key={label}
                              style={[
                                styles.resultTableCell,
                                styles.resultTableHeaderText,
                              ]}
                              >
                              {label}
                              </Text>
                            ))}
                            </View>

                            {metrics.map((item) => {
                              const status =
                              item.status;

                              return (
                                <View
                                key={`result-${item.id}`}
                                style={
                                  styles.resultTableRow
                                }
                                >
                                <Text
                                style={[
                                  styles.resultTableCell,
                                  styles.resultTableId,
                                ]}
                                >
                                {item.id}
                                </Text>

                                <Text
                                style={
                                  styles.resultTableCell
                                }
                                >
                                {String(
                                  item.row?.date ??
                                  "",
                                )}
                                </Text>

                                <Text
                                style={
                                  styles.resultTableCell
                                }
                                >
                                {item.lat.toFixed(4)}
                                </Text>

                                <Text
                                style={
                                  styles.resultTableCell
                                }
                                >
                                {item.lon.toFixed(4)}
                                </Text>

                                <Text
                                style={
                                  styles.resultTableCell
                                }
                                >
                                {item.hpi.toFixed(2)}
                                </Text>

                                <Text
                                style={
                                  styles.resultTableCell
                                }
                                >
                                {item.hei.toFixed(2)}
                                </Text>

                                <Text
                                style={
                                  styles.resultTableCell
                                }
                                >
                                {item.cd.toFixed(2)}
                                </Text>

                                <View
                                style={[
                                  styles.resultStatus,
                                  {
                                    backgroundColor:
                                    status ===
                                    "HIGH" ||
                                    status ===
                                    "CRITICAL"
                                    ? C.mint2
                                    : status ===
                                    "LOW" ||
                                    status ===
                                    "SAFE"
                                    ? C.mint2
                                    : C.mint2,
                                  },
                                ]}
                                >
                                <Text
                                style={[
                                  styles.resultStatusText,
                                  {
                                    color:
                                    status ===
                                    "HIGH" ||
                                    status ===
                                    "CRITICAL"
                                    ? C.danger
                                    : status ===
                                    "LOW" ||
                                    status ===
                                    "SAFE"
                                    ? C.green
                                    : C.warning,
                                  },
                                ]}
                                >
                                {status}
                                </Text>
                                </View>
                                </View>
                              );
                            })}
                            </View>
                            </ScrollView>
                            </View>

                            {/* ==================================================
                              EXPORT
                              ================================================== */}

                              <View
                              style={styles.exportRow}
                              >
                              <Pressable
                              style={
                                styles.importButton
                              }
                              onPress={exportCsv}
                              >
                              <Ionicons
                              name="download-outline"
                              size={19}
                              color={C.white}
                              />

                              <Text
                              style={
                                styles.importButtonText
                              }
                              >
                              Export CSV
                              </Text>
                              </Pressable>

                              <Pressable
                              style={[
                                styles.importButton,
                                styles.pdfButton,
                              ]}
                              onPress={
                                exportPdfSummary
                              }
                              >
                              <Ionicons
                              name="document-text-outline"
                              size={19}
                              color={C.white}
                              />

                              <Text
                              style={
                                styles.importButtonText
                              }
                              >
                              Export PDF summary
                              </Text>
                              </Pressable>

                              <Text
                              style={
                                styles.exportHint
                              }
                              >
                              CSV includes the selected
                              dataset, original measurements,
                 metadata, and calculated indices.
                 PDF uses the browser print dialog.
                 </Text>
                 </View>
                 </>
            )}
            </View>
        );
  }

  /* ============================================================
   *   R EPORT CELL *
   *   ============================================================ */

  function ReportCell({
    label,
    value,
  }: {
    label: string;
    value: string;
  }) {
    return (
      <View
      style={
        styles.reportCell
      }
      >
      <Text
      style={
        styles.reportCellLabel
      }
      >
      {label}
      </Text>

      <Text
      style={
        styles.reportCellValue
      }
      numberOfLines={2}
      >
      {value}
      </Text>
      </View>
    );
  }

  /* ============================================================
   *   P ROFILE     *
   *   ============================================================ */

  function ProfileScreen({
    user,
    signOut,
  }: {
    user: User;
    signOut: () => Promise<void>;
  }) {
    return (
      <View>
      <PageIntro
      eyebrow="ACCOUNT"
      title="Profile"
      description=""
      />

      <View
      style={
        styles.profilePanel
      }
      >
      <Text
      style={
        styles.profileName
      }
      >
      {
        user.full_name
      }
      </Text>

      <Text
      style={
        styles.profileEmail
      }
      >
      {
        user.email
      }
      </Text>

      <View
      style={
        styles.profileIdentity
      }
      >
      <View
      style={
        styles.profileAvatar
      }
      >
      <Text
      style={
        styles.profileAvatarText
      }
      >
      {initials(
        user.full_name,
      )}
      </Text>
      </View>

      <View>
      <Text
      style={
        styles.profileRole
      }
      >
      {
        user.role
      }
      </Text>

      <Text
      style={
        styles.profileType
      }
      >
      {
        user.account_type ||
        "Other"
      }
      </Text>
      </View>
      </View>

      <View
      style={
        styles.profileGrid
      }
      >
      <ReportCell
      label="ORGANIZATION"
      value={
        user.organization ||
        "Not provided"
      }
      />

      <ReportCell
      label="INSTITUTION"
      value={
        user.institution ||
        "Not provided"
      }
      />

      <ReportCell
      label="RESEARCH AREA"
      value={
        user.research_area ||
        "Not provided"
      }
      />

      <View
      style={[
        styles.reportCell,
        {
          flexBasis:
          "100%",
        },
      ]}
      >
      <Text
      style={
        styles.reportCellLabel
      }
      >
      ACCOUNT CREATED
      </Text>

      <Text
      style={
        styles.reportCellValue
      }
      >
      {
        prettyDate(
          user.created_at,
        )
      }
      </Text>
      </View>
      </View>

      <Pressable
      style={({
        pressed,
      }) => [
        styles.signOutButton,
        pressed && {
          opacity: 0.7,
        },
      ]}
      onPress={
        signOut
      }
      >
      <Ionicons
      name="log-out-outline"
      size={18}
      color={
        C.danger
      }
      />

      <Text
      style={
        styles.signOutText
      }
      >
      Sign out
      </Text>
      </Pressable>
      </View>
      </View>
    );
  }

  /* ============================================================
   *   E MPTY STATE *
   *   ============================================================ */

  function EmptyState({
    icon,
    title,
    text,
  }: {
    icon: keyof typeof Ionicons.glyphMap;
    title: string;
    text: string;
  }) {
    return (
      <View
      style={
        styles.empty
      }
      >
      <Ionicons
      name={icon}
      size={28}
      color={
        C.teal
      }
      />

      <Text
      style={
        styles.emptyTitle
      }
      >
      {title}
      </Text>

      <Text
      style={
        styles.emptyText
      }
      >
      {text}
      </Text>
      </View>
    );
  }


  function TemporalTrendAnalysis({
    dataset,
  }: {
    dataset?: Dataset;
  }) {
    const [granularity, setGranularity] = useState<"hour" | "day" | "month" | "year">("month");
    const [selectedMetals, setSelectedMetals] = useState<string[]>(["Pb", "Cd", "As", "Cr", "Cu", "Zn"]);
    const [hovered, setHovered] = useState<{ metal: string; index: number } | null>(null);
    const [zoom, setZoom] = useState(1);
    const [comparison, setComparison] = useState(false);
    const { width: windowWidth } = useWindowDimensions();
    const compact = windowWidth < 900;

    const palette: Record<string, string> = {
      Pb: "#5B5BD6",
      Cd: "#D65B8A",
      As: "#E49A3A",
      Cr: "#1A9B7B",
      Cu: "#2E86DE",
      Zn: "#8E5BD6",
      Ni: "#D65B5B",
      Fe: "#9B6B43",
      Mn: "#4E8E5D",
    };

    const trendData = useMemo(() => {
      const records = dataset?.records || [];
      const groups = new Map<string, { timestamp: number; values: Record<string, number[]> }>();

      records.forEach((row) => {
        const rawDate = sampleDateFor(row);
        if (!rawDate) return;
        const parsed = new Date(String(rawDate).replace(" ", "T"));
        if (Number.isNaN(parsed.getTime())) return;

        let key = "";
        if (granularity === "hour") {
          key = `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, "0")}-${String(parsed.getDate()).padStart(2, "0")} ${String(parsed.getHours()).padStart(2, "0")}:00`;
        } else if (granularity === "day") {
          key = `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, "0")}-${String(parsed.getDate()).padStart(2, "0")}`;
        } else if (granularity === "month") {
          key = `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, "0")}`;
        } else {
          key = String(parsed.getFullYear());
        }

        if (!groups.has(key)) {
          groups.set(key, { timestamp: parsed.getTime(), values: {} });
        }

        const group = groups.get(key)!;
        group.timestamp = Math.min(group.timestamp, parsed.getTime());

        SUPPORTED_METALS.forEach((metal) => {
          const raw = findField(row, [metal]);
          const value = Number(raw);
          if (!Number.isFinite(value)) return;
          if (!group.values[metal]) group.values[metal] = [];
          group.values[metal].push(value);
        });
      });

      return Array.from(groups.entries())
      .map(([label, group]) => ({
        label,
        timestamp: group.timestamp,
        values: Object.fromEntries(
          Object.entries(group.values).map(([metal, values]) => [
            metal,
            values.reduce((sum, value) => sum + value, 0) / values.length,
          ]),
        ) as Record<string, number>,
      }))
      .sort((a, b) => a.timestamp - b.timestamp);
    }, [dataset, granularity]);

    const visibleMetals = selectedMetals.filter((metal) =>
    trendData.some((point) => Number.isFinite(point.values[metal])),
    );

    const values = trendData.flatMap((point) =>
    visibleMetals
    .map((metal) => point.values[metal])
    .filter((value) => Number.isFinite(value)),
    );

    const average = values.length
    ? values.reduce((sum, value) => sum + value, 0) / values.length
    : 0;
    const peak = values.length ? Math.max(...values) : 0;
    const midpoint = Math.max(1, Math.floor(trendData.length / 2));
    const previousPoints = trendData.slice(0, midpoint);
    const currentPoints = trendData.slice(midpoint);
    const previousValues = previousPoints.flatMap((point) =>
    visibleMetals
    .map((metal) => point.values[metal])
    .filter((value) => Number.isFinite(value)),
    );
    const currentValues = currentPoints.flatMap((point) =>
    visibleMetals
    .map((metal) => point.values[metal])
    .filter((value) => Number.isFinite(value)),
    );
    const previousAverage = previousValues.length
    ? previousValues.reduce((sum, value) => sum + value, 0) / previousValues.length
    : 0;
    const currentAverage = currentValues.length
    ? currentValues.reduce((sum, value) => sum + value, 0) / currentValues.length
    : average;
    const changeRate = previousAverage
    ? ((currentAverage - previousAverage) / previousAverage) * 100
    : 0;
    const trendDirection = changeRate > 5 ? "Increasing" : changeRate < -5 ? "Decreasing" : "Stable";

    const mean = values.length ? average : 0;
    const std = values.length > 1
    ? Math.sqrt(values.reduce((sum, value) => sum + Math.pow(value - mean, 2), 0) / values.length)
    : 0;
    const alertIndexes = new Set<number>();
    trendData.forEach((point, index) => {
      if (visibleMetals.some((metal) => {
        const value = point.values[metal];
        return Number.isFinite(value) && std > 0 && value > mean + 2 * std;
      })) {
        alertIndexes.add(index);
      }
    });

    const chartWidth = Math.max(760, 760 * zoom);
    const chartHeight = 320;
    const padding = { left: 52, right: 20, top: 20, bottom: 42 };
    const innerWidth = chartWidth - padding.left - padding.right;
    const innerHeight = chartHeight - padding.top - padding.bottom;
    const maxValue = Math.max(peak, 1);
    const minValue = values.length ? Math.min(...values) : 0;
    const range = Math.max(maxValue - minValue, maxValue * 0.08, 1);
    const yMin = Math.max(0, minValue - range * 0.08);
    const yMax = maxValue + range * 0.08;

    const pointXY = (index: number, value: number) => ({
      x: padding.left + (trendData.length <= 1 ? innerWidth / 2 : (index / (trendData.length - 1)) * innerWidth),
                                                       y: padding.top + innerHeight - ((value - yMin) / Math.max(yMax - yMin, 1)) * innerHeight,
    });

    const makePath = (metal: string) => {
      const points = trendData
      .map((point, index) => {
        const value = point.values[metal];
        if (!Number.isFinite(value)) return null;
        return pointXY(index, value);
      })
      .filter(Boolean) as { x: number; y: number }[];

      if (!points.length) return "";
      if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;

      let path = `M ${points[0].x} ${points[0].y}`;
      for (let i = 1; i < points.length; i += 1) {
        const previous = points[i - 1];
        const current = points[i];
        const controlX = (previous.x + current.x) / 2;
        path += ` C ${controlX} ${previous.y}, ${controlX} ${current.y}, ${current.x} ${current.y}`;
      }
      return path;
    };

    const toggleMetal = (metal: string) => {
      setSelectedMetals((current) =>
      current.includes(metal)
      ? current.filter((item) => item !== metal)
      : [...current, metal],
      );
    };

    const formatLabel = (label: string) => {
      if (granularity === "year") return label;
      if (granularity === "month") return label;
      if (granularity === "day") return label.slice(5);
      return label.slice(11);
    };

    return (
      <View style={styles.temporalPanel}>
      <View style={styles.temporalHeader}>
      <View style={styles.temporalHeaderText}>
      <Text style={styles.panelTitle}>Temporal Trend Analysis</Text>
      <Text style={styles.panelSubtitle}>
      Graph Name: Temporal Pollution Trend Analysis · Historical heavy-metal concentration trends
      </Text>
      </View>
      <View style={styles.temporalHeaderBadge}>
      <Ionicons name="pulse-outline" size={16} color={C.teal} />
      <Text style={styles.temporalHeaderBadgeText}>{alertIndexes.size} alerts</Text>
      </View>
      </View>

      <View style={styles.temporalControls}>
      <View style={styles.temporalControlGroup}>
      <Text style={styles.temporalControlLabel}>TIME SCALE</Text>
      {(["hour", "day", "month", "year"] as const).map((item) => (
        <Pressable
        key={item}
        onPress={() => setGranularity(item)}
        style={[styles.temporalFilter, granularity === item && styles.temporalFilterActive]}
        >
        <Text style={[styles.temporalFilterText, granularity === item && styles.temporalFilterTextActive]}>
        {item === "hour" ? "Hourly" : item === "day" ? "Daily" : item === "month" ? "Monthly" : "Yearly"}
        </Text>
        </Pressable>
      ))}
      </View>

      <View style={styles.temporalControlGroup}>
      <Pressable
      onPress={() => setComparison((value) => !value)}
      style={[styles.temporalAction, comparison && styles.temporalActionActive]}
      >
      <Ionicons name="git-compare-outline" size={15} color={comparison ? C.white : C.teal} />
      <Text style={[styles.temporalActionText, comparison && styles.temporalActionTextActive]}>Compare period</Text>
      </Pressable>
      <Pressable
      onPress={() => setZoom((value) => Math.max(1, Number((value - 0.25).toFixed(2))))}
      style={styles.temporalIconButton}
      >
      <Ionicons name="remove-outline" size={17} color={C.text} />
      </Pressable>
      <Pressable
      onPress={() => setZoom((value) => Math.min(3, Number((value + 0.25).toFixed(2))))}
      style={styles.temporalIconButton}
      >
      <Ionicons name="add-outline" size={17} color={C.text} />
      </Pressable>
      </View>
      </View>

      <View style={styles.temporalLegendWrap}>
      {SUPPORTED_METALS.map((metal) => {
        const active = selectedMetals.includes(metal);
        return (
          <Pressable key={metal} onPress={() => toggleMetal(metal)} style={[styles.temporalLegendItem, !active && styles.temporalLegendItemMuted]}>
          <View style={[styles.temporalLegendDot, { backgroundColor: palette[metal] }]} />
          <Text style={styles.temporalLegendText}>{metal}</Text>
          </Pressable>
        );
      })}
      </View>

      {trendData.length < 2 || visibleMetals.length === 0 ? (
        <View style={styles.temporalEmpty}>
        <Ionicons name="analytics-outline" size={34} color={C.teal} />
        <Text style={styles.temporalEmptyTitle}>Temporal data not available</Text>
        <Text style={styles.temporalEmptyText}>
        Import records containing a valid date or timestamp and metal concentration values to populate this analysis.
        </Text>
        </View>
      ) : (
        <View style={[styles.temporalBody, compact && styles.temporalBodyCompact]}>
        <View style={[styles.temporalMetrics, compact && styles.temporalMetricsCompact]}>
        <View style={styles.temporalMetricCard}>
        <Text style={styles.temporalMetricLabel}>AVERAGE LEVEL</Text>
        <Text style={styles.temporalMetricValue}>{average.toFixed(3)}</Text>
        <Text style={styles.temporalMetricHint}>Selected metals</Text>
        </View>
        <View style={styles.temporalMetricCard}>
        <Text style={styles.temporalMetricLabel}>PEAK LEVEL</Text>
        <Text style={styles.temporalMetricValue}>{peak.toFixed(3)}</Text>
        <Text style={styles.temporalMetricHint}>Maximum observed</Text>
        </View>
        <View style={styles.temporalMetricCard}>
        <Text style={styles.temporalMetricLabel}>TREND DIRECTION</Text>
        <View style={styles.temporalTrendValueRow}>
        <Ionicons
        name={trendDirection === "Increasing" ? "trending-up-outline" : trendDirection === "Decreasing" ? "trending-down-outline" : "remove-outline"}
        size={22}
        color={trendDirection === "Increasing" ? C.danger : trendDirection === "Decreasing" ? C.green : C.warning}
        />
        <Text style={styles.temporalMetricValueSmall}>{trendDirection}</Text>
        </View>
        <Text style={styles.temporalMetricHint}>Based on period change</Text>
        </View>
        <View style={styles.temporalMetricCard}>
        <Text style={styles.temporalMetricLabel}>CHANGE RATE</Text>
        <Text style={styles.temporalMetricValue}>{changeRate >= 0 ? "+" : ""}{changeRate.toFixed(1)}%</Text>
        <Text style={styles.temporalMetricHint}>{comparison ? "Current vs previous" : "First vs latest period"}</Text>
        </View>

        {comparison && (
          <View style={styles.temporalComparisonCard}>
          <View style={styles.temporalComparisonTitleRow}>
          <Ionicons name="git-compare-outline" size={16} color={C.teal} />
          <Text style={styles.temporalComparisonTitle}>Period comparison</Text>
          </View>
          <Text style={styles.temporalComparisonText}>
          Previous average {previousAverage.toFixed(3)} · Current average {currentAverage.toFixed(3)}
          </Text>
          </View>
        )}

        {alertIndexes.size > 0 && (
          <View style={styles.temporalAlertCard}>
          <View style={styles.temporalAlertIcon}>
          <Ionicons name="notifications-outline" size={18} color={C.danger} />
          </View>
          <View style={{ flex: 1 }}>
          <Text style={styles.temporalAlertTitle}>Unusual pollution events detected</Text>
          <Text style={styles.temporalAlertText}>
          {alertIndexes.size} significant spike{alertIndexes.size === 1 ? "" : "s"} exceeded the statistical alert threshold.
          </Text>
          </View>
          </View>
        )}
        </View>

        <View style={styles.temporalChartArea}>
        <View style={styles.temporalChartTopRow}>
        <View>
        <Text style={styles.temporalChartTitle}>Temporal Pollution Trend Analysis</Text>
        <Text style={styles.temporalChartSubtitle}>
        {trendData.length} {granularity === "hour" ? "hourly" : granularity === "day" ? "daily" : granularity === "month" ? "monthly" : "yearly"} periods · concentration level
        </Text>
        </View>
        {hovered && trendData[hovered.index] && (
          <View style={styles.temporalTooltip}>
          <Text style={styles.temporalTooltipTitle}>{hovered.metal}</Text>
          <Text style={styles.temporalTooltipValue}>
          {trendData[hovered.index].values[hovered.metal]?.toFixed(4) ?? "N/A"}
          </Text>
          <Text style={styles.temporalTooltipDate}>{trendData[hovered.index].label}</Text>
          </View>
        )}
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.temporalChartScroll}>
        <Svg width={chartWidth} height={chartHeight}>
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = padding.top + innerHeight * ratio;
          const value = yMax - (yMax - yMin) * ratio;
          return (
            <React.Fragment key={`grid-${ratio}`}>
            <Line x1={padding.left} y1={y} x2={chartWidth - padding.right} y2={y} stroke={C.border} strokeWidth="1" />
            <SvgText x={padding.left - 8} y={y + 3} fill={C.muted} fontSize="8" textAnchor="end">{value.toFixed(2)}</SvgText>
            </React.Fragment>
          );
        })}

        {comparison && visibleMetals.map((metal) => {
          const periodValues = previousPoints
          .map((point) => point.values[metal])
          .filter((value) => Number.isFinite(value));
          if (!periodValues.length) return null;
          const avg = periodValues.reduce((sum, value) => sum + value, 0) / periodValues.length;
          const y = pointXY(0, avg).y;
          return (
            <Line
            key={`previous-${metal}`}
            x1={padding.left}
            y1={y}
            x2={chartWidth - padding.right}
            y2={y}
            stroke={palette[metal]}
            strokeWidth="1"
            strokeDasharray="5 5"
            opacity={0.35}
            />
          );
        })}

        {visibleMetals.map((metal) => (
          <Path
          key={metal}
          d={makePath(metal)}
          fill="none"
          stroke={palette[metal]}
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          />
        ))}

        {visibleMetals.flatMap((metal) =>
          trendData.map((point, index) => {
            const value = point.values[metal];
            if (!Number.isFinite(value)) return null;
            const xy = pointXY(index, value);
            return (
              <Circle
              key={`${metal}-${index}`}
              cx={xy.x}
              cy={xy.y}
              r={alertIndexes.has(index) ? 6 : 4}
              fill={alertIndexes.has(index) ? C.danger : palette[metal]}
              stroke={C.surface}
              strokeWidth="2"
              onPress={() => setHovered({ metal, index })}
              />
            );
          }),
        )}

        {trendData.map((point, index) => {
          if (index !== 0 && index !== trendData.length - 1 && index % Math.max(1, Math.ceil(trendData.length / 6)) !== 0) return null;
          const xy = pointXY(index, yMin);
          return (
            <SvgText key={`x-${index}`} x={xy.x} y={chartHeight - 12} fill={C.muted} fontSize="8" textAnchor="middle">
            {formatLabel(point.label)}
            </SvgText>
          );
        })}
        </Svg>
        </ScrollView>

        <View style={styles.temporalAxisNote}>
        <Text style={styles.temporalAxisText}>Time →</Text>
        <View style={styles.temporalAxisRight}>
        <Ionicons name="hand-left-outline" size={13} color={C.muted} />
        <Text style={styles.temporalAxisText}>Scroll to pan · + / − to zoom · tap a point for exact value</Text>
        </View>
        </View>
        </View>
        </View>
      )}
      </View>
    );
  }

  /* ============================================================
   *   S TYLES      *
   *   ============================================================ */

  function createStyles() {
    return StyleSheet.create({
      center: {
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: C.bg,
      },

      googleMap: {
        width: "100%",
        height: 520,
        borderRadius: 16,
        overflow: "hidden",
      },

      mapFallback: {
        minHeight: 280,
        borderRadius: 16,
        borderWidth: 1,
        borderColor: C.border,
        backgroundColor: C.mint2,
        alignItems: "center",
        justifyContent: "center",
        padding: 28,
      },

      mapFallbackTitle: {
        marginTop: 10,
        fontSize: 17,
        fontWeight: "700",
        color: C.text,
      },

      mapFallbackText: {
        marginTop: 8,
        maxWidth: 430,
        textAlign: "center",
        lineHeight: 20,
        color: C.muted,
      },

      legendRow: {
        flexDirection: "row",
        flexWrap: "wrap",
        gap: 20,
      },

      legendItem: {
        flexDirection: "row",
        alignItems: "center",
        gap: 7,
      },

      legendDot: {
        width: 10,
        height: 10,
        borderRadius: 5,
      },

      legendText: {
        fontSize: 12,
        fontWeight: "700",
        color: C.text,
      },

      authWrap: {
        flex: 1,
        backgroundColor: C.bg,
      },

      authScroll: {
        minHeight:
        Dimensions.get(
          "window",
        ).height,
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      },

      brand: {
        alignItems: "center",
        marginBottom: 34,
      },

      logo: {
        width: 52,
        height: 52,
        borderRadius: 14,
        backgroundColor: C.teal,
        alignItems: "center",
        justifyContent: "center",
        marginBottom: 12,
      },

      brandName: {
        fontSize: 27,
        fontWeight: "800",
        color: C.text,
      },

      tagline: {
        marginTop: 4,
        color: C.muted,
        fontSize: 14,
      },

      authCard: {
        width: "100%",
        maxWidth: 440,
        backgroundColor: C.surface,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 18,
        padding: 28,
      },

      eyebrow: {
        color: C.teal,
        fontSize: 11,
        letterSpacing: 2,
        fontWeight: "800",
        marginBottom: 10,
      },

      h1: {
        color: C.text,
        fontSize: 30,
        fontWeight: "800",
        marginBottom: 10,
      },

      sub: {
        color: C.muted,
        fontSize: 15,
        lineHeight: 23,
        marginBottom: 25,
      },

      fieldWrap: {
        marginBottom: 16,
      },

      fieldLabel: {
        color: C.muted,
        fontSize: 11,
        letterSpacing: 1.4,
        fontWeight: "800",
        marginBottom: 8,
      },

      input: {
        height: 48,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 10,
        paddingHorizontal: 14,
        color: C.text,
        backgroundColor: C.surface,
        fontSize: 15,
      },

      passwordBox: {
        height: 48,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 10,
        paddingLeft: 14,
        paddingRight: 13,
        flexDirection: "row",
        alignItems: "center",
        marginBottom: 16,
      },

      passwordInput: {
        flex: 1,
        color: C.text,
        fontSize: 15,
      },

      authError: {
        color: C.danger,
        fontSize: 13,
        marginBottom: 14,
      },

      primaryButton: {
        height: 48,
        borderRadius: 10,
        backgroundColor: C.green,
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "row",
        gap: 8,
        marginTop: 2,
      },

      primaryButtonText: {
        color: C.white,
        fontSize: 15,
        fontWeight: "800",
      },

      authSwitch: {
        color: C.teal,
        textAlign: "center",
        fontWeight: "800",
        fontSize: 14,
        marginTop: 19,
      },

      shell: {
        flex: 1,
        flexDirection: "row",
        backgroundColor: C.bg,
      },

      sidebar: {
        width: 375,
        backgroundColor: C.sidebar,
        borderRightWidth: 1,
        borderRightColor: C.border,
        paddingHorizontal: 17,
        paddingTop: 22,
        paddingBottom: 17,
      },

      sidebarMobile: {
        position: "absolute",
        zIndex: 100,
        left: 0,
        top: 0,
        bottom: 0,
        elevation: 20,
      },

      sidebarBrand: {
        flexDirection: "row",
        alignItems: "center",
        paddingHorizontal: 5,
        marginBottom: 43,
      },

      sidebarLogo: {
        width: 51,
        height: 51,
        marginRight: 14,
        resizeMode: "contain",
      },
      sidebarBrandText: {
        color: C.text,
        fontSize: 20,
        fontWeight: "800",
      },

      workspaceLabel: {
        color: C.muted,
        fontSize: 10,
        fontWeight: "800",
        letterSpacing: 1.5,
        marginHorizontal: 5,
        marginBottom: 14,
      },

      navList: {
        gap: 5,
      },

      navItem: {
        minHeight: 68,
        borderRadius: 15,
        paddingHorizontal: 15,
        flexDirection: "row",
        alignItems: "center",
        gap: 20,
      },

      navItemActive: {
        backgroundColor: C.mint,
        borderWidth: 2,
        borderColor: C.border,
      },

      navText: {
        color: C.muted,
        fontSize: 20,
        fontWeight: "500",
      },

      navTextActive: {
        color: C.greenDark,
        fontWeight: "800",
      },

      sidebarBottom: {
        marginTop: "auto",
      },

      sidebarDivider: {
        height: 1,
        backgroundColor: C.border,
        marginBottom: 15,
      },

      userMini: {
        flexDirection: "row",
        alignItems: "center",
        gap: 9,
      },

      avatarSmall: {
        width: 36,
        height: 36,
        borderRadius: 11,
        backgroundColor: C.mint,
        alignItems: "center",
        justifyContent: "center",
      },

      avatarLetter: {
        color: C.green,
        fontWeight: "800",
        fontSize: 16,
      },

      userMiniName: {
        color: C.text,
        fontWeight: "800",
        fontSize: 12.5,
      },

      userMiniRole: {
        color: C.muted,
        fontSize: 11,
        marginTop: 2,
      },

      main: {
        flex: 1,
        minWidth: 0,
      },

      topbar: {
        height: 74,
        backgroundColor: C.surface,
        borderBottomWidth: 1,
        borderBottomColor: C.border,
        flexDirection: "row",
        alignItems: "center",
        paddingHorizontal: 38,
      },

      mobileMenu: {
        display: "none",
        marginRight: 14,
      },

      topbarTitle: {
        flex: 1,
        flexDirection: "row",
        alignItems: "center",
        gap: 18,
      },

      topTitle: {
        color: C.text,
        fontSize: 19,
        fontWeight: "800",
      },

      topSubtitle: {
        color: C.muted,
        fontSize: 12,
        marginTop: 2,
      },

      topAvatar: {
        width: 38,
        height: 38,
        borderRadius: 12,
        backgroundColor: C.mint,
        alignItems: "center",
        justifyContent: "center",
      },

      topAvatarText: {
        color: C.green,
        fontWeight: "800",
      },

      content: {
        flex: 1,
        backgroundColor: C.bg,
      },

      contentInner: {
        paddingHorizontal: 30,
        paddingVertical: 29,
        maxWidth: 1350,
        width: "100%",
        alignSelf: "center",
      },

      pageIntro: {
        marginBottom: 28,
      },

      pageEyebrow: {
        color: C.teal,
        fontSize: 11,
        letterSpacing: 2,
        fontWeight: "800",
        marginBottom: 7,
      },

      pageTitle: {
        color: C.text,
        fontSize: 31,
        lineHeight: 38,
        fontWeight: "800",
        marginBottom: 9,
      },

      pageDescription: {
        color: C.muted,
        fontSize: 15,
        lineHeight: 23,
        maxWidth: 820,
      },

      heroCard: {
        minHeight: 270,
        backgroundColor: C.surface,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 18,
        padding: 32,
        flexDirection: "row",
        alignItems: "center",
        gap: 30,
        marginBottom: 20,
      },

      heroEyebrow: {
        color: C.teal,
        fontSize: 14,
        letterSpacing: 2.5,
        fontWeight: "800",
        marginBottom: 12,
      },

      heroTitle: {
        color: C.text,
        fontSize: 40,
        lineHeight: 48,
        fontWeight: "800",
        maxWidth: 650,
      },

      heroText: {
        color: C.muted,
        fontSize: 15,
        lineHeight: 23,
        marginTop: 12,
        maxWidth: 540,
      },

      importButton: {
        backgroundColor: C.green,
        borderRadius: 9,
        height: 47,
        paddingHorizontal: 18,
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
      },

      importButtonText: {
        color: C.white,
        fontSize: 14,
        fontWeight: "800",
      },

      analysisHeader: {
        flexDirection: "row",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: 24,
        marginBottom: 28,
        position: "relative",
        zIndex: 100,
      },

      analysisHeaderText: {
        flex: 1,
        minWidth: 0,
      },

      statRow: {
        flexDirection: "row",
        gap: 15,
        marginBottom: 15,
      },

      sampleSelectorPanel: {
        width: 360,
        maxWidth: "42%",
        backgroundColor: C.surface,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 12,
        padding: 12,
        marginBottom: 0,
        position: "relative",
        zIndex: 200,
      },

      sampleSelectorHeader: {
        flexDirection: "row",
        alignItems: "center",
        marginBottom: 7,
      },

      sampleSelectorTitle: {
        color: C.teal,
        fontSize: 11,
        fontWeight: "800",
        letterSpacing: 0.7,
        textTransform: "uppercase",
      },

      sampleSelectorSubtitle: {
        color: C.muted,
        fontSize: 11,
        marginTop: 3,
      },

      sampleSelectorButton: {
        minHeight: 48,
        borderWidth: 1,
        borderColor: C.teal,
        borderRadius: 8,
        paddingHorizontal: 13,
        paddingVertical: 7,
        flexDirection: "row",
        alignItems: "center",
        backgroundColor: C.bg,
      },

      sampleSelectorValue: {
        color: C.text,
        fontSize: 13,
        fontWeight: "800",
      },

      sampleSelectorMeta: {
        color: C.muted,
        fontSize: 10,
        marginTop: 2,
      },

      sampleDropdown: {
        position: "absolute",
        left: 12,
        right: 12,
        top: 78,
        backgroundColor: C.surface,
        borderWidth: 1,
        borderColor: C.teal,
        borderRadius: 8,
        zIndex: 100,
        elevation: 12,
        shadowColor: "#000000",
        shadowOpacity: 0.2,
        shadowRadius: 8,
        shadowOffset: { width: 0, height: 4 },
      },

      sampleDropdownScroll: {
        maxHeight: 320,
      },

      sampleDropdownOption: {
        minHeight: 54,
        paddingHorizontal: 12,
        paddingVertical: 8,
        flexDirection: "row",
        alignItems: "center",
        gap: 9,
        borderBottomWidth: 1,
        borderBottomColor: C.border,
      },

      sampleDropdownOptionActive: {
        backgroundColor: C.mint2,
      },

      sampleDropdownName: {
        color: C.text,
        fontSize: 12,
        fontWeight: "800",
      },

      sampleDropdownMeta: {
        color: C.muted,
        fontSize: 10,
        marginTop: 2,
      },

      sampleDropdownMetrics: {
        alignItems: "flex-end",
        marginRight: 6,
      },

      sampleDropdownMetric: {
        color: C.muted,
        fontSize: 9,
        lineHeight: 13,
      },

      gaugeRow: {
        flexDirection: "row",
        gap: 15,
        marginBottom: 15,
      },

      gaugeCard: {
        flex: 1,
        height: 177,
        backgroundColor: C.surface,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 9,
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
        position: "relative",
      },

      gaugeValueContainer: {
        position: "absolute",
        top: 88,
        left: 0,
        right: 0,
        alignItems: "center",
      },

      gaugeValue: {
        color: C.text,
        fontSize: 20,
        lineHeight: 24,
        fontWeight: "900",
      },

      gaugeStatus: {
        fontSize: 9,
        lineHeight: 13,
        fontWeight: "800",
        marginTop: 2,
      },

      gaugeLabel: {
        color: C.muted,
        fontSize: 10,
        lineHeight: 14,
        marginTop: 1,
      },

      statCard: {
        flex: 1,
        minHeight: 150,
        backgroundColor: C.surface,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 15,
        padding: 24,
      },

      statValue: {
        color: C.text,
        fontSize: 32,
        fontWeight: "800",
        marginTop: 12,
      },

      metricValue: {
        color: C.text,
        fontSize: 27,
        fontWeight: "800",
        marginTop: 9,
      },

      statLabel: {
        color: C.muted,
        fontSize: 12,
        marginTop: 2,
      },

      singleStat: {
        minHeight: 135,
        backgroundColor: C.surface,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 15,
        padding: 24,
        marginBottom: 15,
      },

      bigStat: {
        color: C.text,
        fontSize: 32,
        fontWeight: "800",
        marginTop: 12,
      },

      temporalPanel: {
        backgroundColor: C.surface,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 18,
        padding: 24,
        marginBottom: 15,
        shadowColor: "#000000",
        shadowOpacity: 0.06,
        shadowRadius: 10,
        shadowOffset: { width: 0, height: 4 },
        elevation: 2,
      },

      temporalHeader: {
        flexDirection: "row",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: 14,
        marginBottom: 16,
      },

      temporalHeaderText: {
        flex: 1,
        minWidth: 0,
      },

      temporalHeaderBadge: {
        flexDirection: "row",
        alignItems: "center",
        gap: 6,
        borderWidth: 1,
        borderColor: C.border,
        backgroundColor: C.mint2,
        borderRadius: 999,
        paddingHorizontal: 10,
        paddingVertical: 7,
      },

      temporalHeaderBadgeText: {
        color: C.text,
        fontSize: 11,
        fontWeight: "800",
      },

      temporalControls: {
        flexDirection: "row",
        justifyContent: "space-between",
        alignItems: "center",
        flexWrap: "wrap",
        gap: 12,
        marginBottom: 13,
      },

      temporalControlGroup: {
        flexDirection: "row",
        alignItems: "center",
        flexWrap: "wrap",
        gap: 7,
      },

      temporalControlLabel: {
        color: C.muted,
        fontSize: 9,
        fontWeight: "800",
        letterSpacing: 1,
        marginRight: 2,
      },

      temporalFilter: {
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 8,
        paddingHorizontal: 10,
        paddingVertical: 7,
        backgroundColor: C.surface,
      },

      temporalFilterActive: {
        backgroundColor: C.mint,
        borderColor: C.teal,
      },

      temporalFilterText: {
        color: C.muted,
        fontSize: 10,
        fontWeight: "700",
      },

      temporalFilterTextActive: {
        color: C.teal,
      },

      temporalAction: {
        flexDirection: "row",
        alignItems: "center",
        gap: 6,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 8,
        paddingHorizontal: 10,
        paddingVertical: 7,
        backgroundColor: C.surface,
      },

      temporalActionActive: {
        backgroundColor: C.teal,
        borderColor: C.teal,
      },

      temporalActionText: {
        color: C.teal,
        fontSize: 10,
        fontWeight: "800",
      },

      temporalActionTextActive: {
        color: C.white,
      },

      temporalIconButton: {
        width: 32,
        height: 32,
        borderRadius: 8,
        borderWidth: 1,
        borderColor: C.border,
        backgroundColor: C.surface,
        alignItems: "center",
        justifyContent: "center",
      },

      temporalLegendWrap: {
        flexDirection: "row",
        flexWrap: "wrap",
        gap: 8,
        marginBottom: 16,
      },

      temporalLegendItem: {
        flexDirection: "row",
        alignItems: "center",
        gap: 5,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 999,
        paddingHorizontal: 9,
        paddingVertical: 5,
        backgroundColor: C.surface,
      },

      temporalLegendItemMuted: {
        opacity: 0.35,
      },

      temporalLegendDot: {
        width: 8,
        height: 8,
        borderRadius: 4,
      },

      temporalLegendText: {
        color: C.text,
        fontSize: 10,
        fontWeight: "800",
      },

      temporalBody: {
        flexDirection: "row",
        alignItems: "stretch",
        gap: 18,
      },

      temporalBodyCompact: {
        flexDirection: "column",
      },

      temporalMetrics: {
        width: 245,
        minWidth: 210,
        gap: 10,
      },

      temporalMetricsCompact: {
        width: "100%",
        minWidth: 0,
      },

      temporalMetricCard: {
        backgroundColor: C.mint2,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 11,
        padding: 13,
        minHeight: 78,
      },

      temporalMetricLabel: {
        color: C.muted,
        fontSize: 9,
        fontWeight: "800",
        letterSpacing: 1,
      },

      temporalMetricValue: {
        color: C.text,
        fontSize: 22,
        fontWeight: "900",
        marginTop: 5,
      },

      temporalMetricValueSmall: {
        color: C.text,
        fontSize: 16,
        fontWeight: "900",
        marginLeft: 6,
      },

      temporalMetricHint: {
        color: C.muted,
        fontSize: 9,
        marginTop: 2,
      },

      temporalTrendValueRow: {
        flexDirection: "row",
        alignItems: "center",
        marginTop: 5,
      },

      temporalComparisonCard: {
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 11,
        padding: 12,
        backgroundColor: C.surface,
      },

      temporalComparisonTitleRow: {
        flexDirection: "row",
        alignItems: "center",
        gap: 6,
      },

      temporalComparisonTitle: {
        color: C.text,
        fontSize: 10,
        fontWeight: "800",
      },

      temporalComparisonText: {
        color: C.muted,
        fontSize: 9,
        lineHeight: 14,
        marginTop: 5,
      },

      temporalAlertCard: {
        flexDirection: "row",
        alignItems: "center",
        gap: 9,
        borderWidth: 1,
        borderColor: C.danger,
        borderRadius: 11,
        padding: 11,
        backgroundColor: C.surface,
      },

      temporalAlertIcon: {
        width: 31,
        height: 31,
        borderRadius: 10,
        backgroundColor: C.mint2,
        alignItems: "center",
        justifyContent: "center",
      },

      temporalAlertTitle: {
        color: C.text,
        fontSize: 10,
        fontWeight: "800",
      },

      temporalAlertText: {
        color: C.muted,
        fontSize: 9,
        lineHeight: 13,
        marginTop: 2,
      },

      temporalChartArea: {
        flex: 1,
        minWidth: 0,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 13,
        padding: 14,
        backgroundColor: C.surface,
        overflow: "hidden",
      },

      temporalChartTopRow: {
        minHeight: 52,
        flexDirection: "row",
        justifyContent: "space-between",
        alignItems: "flex-start",
        gap: 10,
      },

      temporalChartTitle: {
        color: C.text,
        fontSize: 14,
        fontWeight: "800",
      },

      temporalChartSubtitle: {
        color: C.muted,
        fontSize: 9,
        marginTop: 3,
      },

      temporalTooltip: {
        minWidth: 115,
        borderWidth: 1,
        borderColor: C.teal,
        borderRadius: 9,
        paddingHorizontal: 9,
        paddingVertical: 7,
        backgroundColor: C.mint2,
      },

      temporalTooltipTitle: {
        color: C.text,
        fontSize: 10,
        fontWeight: "800",
      },

      temporalTooltipValue: {
        color: C.teal,
        fontSize: 14,
        fontWeight: "900",
        marginTop: 2,
      },

      temporalTooltipDate: {
        color: C.muted,
        fontSize: 8,
        marginTop: 1,
      },

      temporalChartScroll: {
        width: "100%",
      },

      temporalAxisNote: {
        flexDirection: "row",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 10,
        marginTop: 2,
      },

      temporalAxisRight: {
        flexDirection: "row",
        alignItems: "center",
        gap: 4,
      },

      temporalAxisText: {
        color: C.muted,
        fontSize: 8,
      },

      temporalEmpty: {
        minHeight: 250,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 13,
        backgroundColor: C.mint2,
        alignItems: "center",
        justifyContent: "center",
        padding: 28,
      },

      temporalEmptyTitle: {
        color: C.text,
        fontSize: 15,
        fontWeight: "800",
        marginTop: 10,
      },

      temporalEmptyText: {
        color: C.muted,
        fontSize: 11,
        lineHeight: 18,
        textAlign: "center",
        maxWidth: 500,
        marginTop: 5,
      },

      panel: {
        backgroundColor: C.surface,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 15,
        padding: 24,
        marginBottom: 15,
      },

      panelTitle: {
        color: C.text,
        fontSize: 17,
        fontWeight: "800",
      },

      panelSubtitle: {
        color: C.muted2,
        fontSize: 11,
        marginTop: 3,
        marginBottom: 13,
      },

      sampleRow: {
        minHeight: 58,
        borderBottomWidth: 1,
        borderBottomColor: C.border,
        flexDirection: "row",
        alignItems: "center",
        paddingVertical: 10,
        gap: 10,
      },

      statusDot: {
        width: 10,
        height: 10,
        borderRadius: 5,
      },

      sampleTitle: {
        color: C.text,
        fontSize: 13,
        fontWeight: "800",
      },

      sampleMeta: {
        color: C.muted,
        fontSize: 10.5,
        marginTop: 3,
      },

      sampleRight: {
        alignItems: "flex-end",
        minWidth: 115,
      },

      sampleHpi: {
        color: C.text,
        fontSize: 12,
        fontWeight: "800",
      },

      sampleHei: {
        color: C.muted,
        fontSize: 10,
        marginTop: 3,
      },

      templatePanel: {
        backgroundColor: C.surface,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 15,
        padding: 24,
        marginBottom: 15,
        shadowColor: "#000000",
        shadowOpacity: 0.05,
        shadowRadius: 8,
        shadowOffset: { width: 0, height: 3 },
        elevation: 2,
      },

      templateHeaderRow: {
        flexDirection: "row",
        alignItems: "flex-start",
        gap: 16,
      },

      templateFieldCount: {
        minWidth: 86,
        paddingHorizontal: 12,
        paddingVertical: 9,
        borderRadius: 11,
        backgroundColor: C.mint2,
        alignItems: "center",
      },

      templateFieldCountValue: {
        color: C.teal,
        fontSize: 20,
        fontWeight: "900",
      },

      templateFieldCountLabel: {
        color: C.muted,
        fontSize: 8,
        fontWeight: "900",
        letterSpacing: 0.8,
        marginTop: 2,
      },

      templateContent: {
        flexDirection: "row",
        gap: 22,
        marginTop: 8,
      },

      templateInfoSection: {
        flex: 1.65,
        minWidth: 0,
      },

      templateContentNarrow: {
        flexDirection: "column",
      },

      templateDownloadSection: {
        flex: 0.9,
        minWidth: 270,
        padding: 16,
        borderRadius: 13,
        backgroundColor: C.mint2,
        borderWidth: 1,
        borderColor: C.border,
      },

      templateDownloadSectionNarrow: {
        minWidth: 0,
        width: "100%",
      },

      templateInfoRow: {
        flexDirection: "row",
        alignItems: "flex-start",
        gap: 10,
        paddingVertical: 8,
      },

      templateInfoTitle: {
        color: C.text,
        fontSize: 12,
        fontWeight: "800",
      },

      templateInfoText: {
        color: C.muted,
        fontSize: 10.5,
        lineHeight: 16,
        marginTop: 2,
      },

      templateValidationBox: {
        flexDirection: "row",
        alignItems: "flex-start",
        gap: 10,
        padding: 11,
        marginTop: 7,
        borderRadius: 10,
        borderWidth: 1,
        borderColor: C.border,
        backgroundColor: C.surface,
      },

      templateGuideHeader: {
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        marginTop: 13,
        marginBottom: 8,
      },

      templateGuideTitle: {
        color: C.text,
        fontSize: 12,
        fontWeight: "800",
      },

      templateCopyButton: {
        flexDirection: "row",
        alignItems: "center",
        gap: 5,
        paddingHorizontal: 9,
        paddingVertical: 6,
        borderRadius: 8,
        borderWidth: 1,
        borderColor: C.border,
        backgroundColor: C.surface,
      },

      templateCopyText: {
        color: C.teal,
        fontSize: 10,
        fontWeight: "800",
      },

      templateFieldGrid: {
        flexDirection: "row",
        flexWrap: "wrap",
        gap: 7,
      },

      templateFieldItem: {
        flexBasis: "48%",
        minWidth: 210,
        minHeight: 34,
        flexDirection: "row",
        alignItems: "center",
        gap: 5,
        paddingHorizontal: 8,
        paddingVertical: 6,
        borderRadius: 8,
        borderWidth: 1,
        borderColor: C.border,
        backgroundColor: C.surface,
      },

      templateFieldName: {
        color: C.text,
        fontSize: 9.5,
        fontWeight: "700",
      },

      templateTooltipText: {
        color: C.muted,
        fontSize: 9,
        lineHeight: 13,
        marginTop: 3,
      },

      templateDownloadTitle: {
        color: C.text,
        fontSize: 14,
        fontWeight: "800",
      },

      templateDownloadText: {
        color: C.muted,
        fontSize: 10.5,
        lineHeight: 15,
        marginTop: 4,
        marginBottom: 12,
      },

      templateDownloadButton: {
        minHeight: 67,
        flexDirection: "row",
        alignItems: "center",
        gap: 10,
        padding: 11,
        borderRadius: 10,
        borderWidth: 1,
        borderColor: C.border,
        backgroundColor: C.surface,
        marginBottom: 9,
      },

      templateDownloadIcon: {
        width: 38,
        height: 38,
        borderRadius: 10,
        backgroundColor: C.mint2,
        alignItems: "center",
        justifyContent: "center",
      },

      templateDownloadButtonTitle: {
        color: C.text,
        fontSize: 11.5,
        fontWeight: "800",
      },

      templateDownloadButtonText: {
        color: C.muted,
        fontSize: 9.5,
        marginTop: 3,
      },

      templatePreviewButton: {
        minHeight: 43,
        borderRadius: 9,
        borderWidth: 1,
        borderColor: C.border,
        backgroundColor: C.surface,
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        gap: 7,
        marginTop: 3,
      },

      templatePreviewText: {
        color: C.text,
        fontSize: 11,
        fontWeight: "800",
      },

      templateStatus: {
        flexDirection: "row",
        alignItems: "center",
        gap: 6,
        marginTop: 10,
      },

      templateStatusText: {
        flex: 1,
        color: C.greenDark,
        fontSize: 9.5,
        fontWeight: "700",
      },

      templateModalBackdrop: {
        flex: 1,
        backgroundColor: "rgba(0,0,0,0.45)",
                             alignItems: "center",
                             justifyContent: "center",
                             padding: 20,
      },

      templateModal: {
        width: "100%",
        maxWidth: 1180,
        maxHeight: "85%",
        backgroundColor: C.surface,
        borderRadius: 16,
        padding: 20,
        borderWidth: 1,
        borderColor: C.border,
      },

      templateModalHeader: {
        flexDirection: "row",
        alignItems: "center",
        gap: 12,
      },

      templateModalTitle: {
        color: C.text,
        fontSize: 18,
        fontWeight: "800",
      },

      templateModalSubtitle: {
        color: C.muted,
        fontSize: 10.5,
        marginTop: 3,
      },

      templatePreviewRow: {
        flexDirection: "row",
        borderBottomWidth: 1,
        borderBottomColor: C.border,
      },

      templatePreviewHeader: {
        backgroundColor: C.mint2,
        borderTopLeftRadius: 8,
        borderTopRightRadius: 8,
      },

      templatePreviewCell: {
        width: 150,
        color: C.text,
        fontSize: 9,
        paddingHorizontal: 8,
        paddingVertical: 9,
        borderRightWidth: 1,
        borderRightColor: C.border,
      },

      templatePreviewHeaderText: {
        color: C.muted,
        fontWeight: "900",
        fontSize: 8.5,
      },

      metadataGrid: {
        flexDirection: "row",
        flexWrap: "wrap",
        gap: 12,
      },

      metadataGridField: {
        flexBasis: "48%",
        minWidth: 260,
      },

      checkRow: {
        minHeight: 70,
        borderBottomWidth: 1,
        borderBottomColor: C.border,
        flexDirection: "row",
        alignItems: "center",
        gap: 12,
        paddingVertical: 10,
      },

      checkIcon: {
        width: 34,
        height: 34,
        borderRadius: 10,
        alignItems: "center",
        justifyContent: "center",
      },

      checkTitle: {
        color: C.text,
        fontSize: 13,
        fontWeight: "800",
      },

      checkMeta: {
        color: C.muted,
        fontSize: 10.5,
        marginTop: 3,
      },

      checkBadge: {
        minWidth: 68,
        paddingHorizontal: 10,
        paddingVertical: 6,
        borderRadius: 999,
        alignItems: "center",
      },

      checkBadgeText: {
        fontSize: 9,
        fontWeight: "900",
        letterSpacing: 0.8,
      },

      sectionHeadingRow: {
        flexDirection: "row",
        alignItems: "center",
        marginBottom: 10,
        marginTop: 4,
      },

      sectionHeading: {
        color: C.muted,
        fontSize: 11,
        letterSpacing: 1.7,
        fontWeight: "800",
      },

      decisionCard: {
        backgroundColor: C.surface,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 15,
        padding: 17,
        flexDirection: "row",
        alignItems: "flex-start",
        gap: 14,
        marginBottom: 10,
      },

      decisionIcon: {
        width: 42,
        height: 42,
        borderRadius: 11,
        alignItems: "center",
        justifyContent: "center",
      },

      decisionTitle: {
        color: C.text,
        fontSize: 15,
        fontWeight: "800",
      },

      decisionText: {
        color: C.muted,
        fontSize: 13,
        lineHeight: 20,
        marginTop: 5,
      },

      resultsTable: {
        minWidth: 1100,
      },

      resultTableRow: {
        minHeight: 56,
        flexDirection: "row",
        alignItems: "center",
        borderBottomWidth: 1,
        borderBottomColor: C.border,
        paddingVertical: 8,
      },

      resultTableHeader: {
        backgroundColor: C.mint2,
        borderRadius: 8,
      },

      resultTableCell: {
        width: 145,
        color: C.text,
        fontSize: 10.5,
        paddingHorizontal: 9,
      },

      resultTableId: {
        width: 85,
        fontWeight: "800",
      },

      resultTableHeaderText: {
        color: C.muted,
        fontSize: 9,
        fontWeight: "900",
        letterSpacing: 0.7,
        textTransform: "uppercase",
      },

      resultStatus: {
        width: 105,
        marginHorizontal: 5,
        paddingVertical: 6,
        borderRadius: 999,
        alignItems: "center",
      },

      resultStatusText: {
        fontSize: 9,
        fontWeight: "900",
      },

      qualityHero: {
        backgroundColor: C.mint,
        borderRadius: 15,
        padding: 25,
        marginBottom: 20,
      },

      qualityEyebrow: {
        color: C.teal,
        fontSize: 11,
        fontWeight: "800",
        letterSpacing: 1.6,
      },

      qualityScoreLine: {
        flexDirection: "row",
        alignItems: "baseline",
        marginTop: 8,
      },

      qualityScore: {
        color: C.green,
        fontSize: 48,
        lineHeight: 55,
        fontWeight: "800",
      },

      qualityOutOf: {
        color: C.muted,
        fontSize: 18,
        fontWeight: "700",
        marginLeft: 8,
      },

      qualityGrade: {
        color: C.text,
        fontSize: 14,
        marginTop: 2,
      },

      importLockedBanner: {
        flexDirection: "row",
        alignItems: "center",
        gap: 12,
        marginTop: 14,
        padding: 13,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: C.warning,
        backgroundColor: C.mint2,
      },

      importLockedIcon: {
        width: 36,
        height: 36,
        borderRadius: 10,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: C.mint,
      },

      importLockedTitle: {
        color: C.text,
        fontSize: 12,
        fontWeight: "800",
      },

      importLockedText: {
        color: C.muted,
        fontSize: 11,
        lineHeight: 16,
        marginTop: 2,
      },

      importReadyBanner: {
        flexDirection: "row",
        alignItems: "center",
        gap: 10,
        marginTop: 14,
        padding: 12,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: C.border,
        backgroundColor: C.mint2,
      },

      importReadyIcon: {
        width: 34,
        height: 34,
        borderRadius: 10,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: C.mint2,
      },

      importReadyText: {
        flex: 1,
        color: C.greenDark,
        fontSize: 11,
        fontWeight: "700",
      },

      importChoiceDisabled: {
        opacity: 0.55,
        backgroundColor: C.surface,
        borderColor: C.border,
      },

      importChoiceIcon: {
        width: 42,
        height: 42,
        borderRadius: 11,
        alignItems: "center",
        justifyContent: "center",
      },

      importChoiceIconDisabled: {
        backgroundColor: C.surface,
      },

      importChoiceTitleDisabled: {
        color: C.muted,
      },

      importChoiceSubtitleDisabled: {
        color: C.muted2,
      },

      importChoiceLockedText: {
        marginTop: 14,
        color: C.muted,
        fontSize: 12,
        fontWeight: "700",
      },

      importChoiceRow: {
        flexDirection: "row",
        gap: 15,
        marginBottom: 20,
      },

      importChoice: {
        flex: 1,
        minHeight: 190,
        backgroundColor: C.surface,
        borderWidth: 1,
        borderStyle: "dashed",
        borderColor: C.border,
        borderRadius: 15,
        padding: 22,
        justifyContent: "center",
      },

      importChoiceTitle: {
        color: C.text,
        fontSize: 17,
        fontWeight: "800",
        marginTop: 17,
      },

      importChoiceSubtitle: {
        color: C.text,
        fontSize: 13,
        marginTop: 8,
      },

      browseText: {
        color: C.green,
        fontSize: 14,
        fontWeight: "800",
        marginTop: 17,
      },

      loadingBanner: {
        flexDirection: "row",
        alignItems: "center",
        gap: 9,
        backgroundColor: C.mint2,
        borderRadius: 10,
        padding: 12,
        marginBottom: 14,
      },

      loadingText: {
        color: C.text,
        fontSize: 13,
      },

      datasetItem: {
        minHeight: 62,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 10,
        padding: 10,
        flexDirection: "row",
        alignItems: "center",
        gap: 10,
      },

      datasetName: {
        color: C.text,
        fontSize: 13,
        fontWeight: "800",
      },

      datasetMeta: {
        color: C.muted,
        fontSize: 10,
        marginTop: 3,
      },

      datasetScore: {
        alignItems: "center",
        minWidth: 52,
      },

      datasetScoreValue: {
        color: C.green,
        fontSize: 17,
        fontWeight: "800",
      },

      datasetScoreLabel: {
        color: C.muted,
        fontSize: 9,
      },

      bullet: {
        color: C.text,
        fontSize: 13,
        lineHeight: 31,
      },

      empty: {
        alignItems: "center",
        paddingVertical: 30,
      },

      emptyTitle: {
        color: C.text,
        fontWeight: "800",
        fontSize: 15,
        marginTop: 9,
      },

      emptyText: {
        color: C.muted,
        fontSize: 12,
        marginTop: 4,
        textAlign: "center",
      },

      reportGrid: {
        flexDirection: "row",
        flexWrap: "wrap",
        gap: 10,
      },

      reportCell: {
        flexGrow: 1,
        flexBasis: "30%",
        minHeight: 67,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 10,
        padding: 12,
        justifyContent: "center",
      },

      reportCellLabel: {
        color: C.muted,
        fontSize: 9.5,
        letterSpacing: 1,
        fontWeight: "800",
        marginBottom: 5,
      },

      reportCellValue: {
        color: C.text,
        fontSize: 15,
        fontWeight: "800",
      },

      reportDatasetList: {
        marginTop: 4,
      },

      reportDatasetOption: {
        flexDirection: "row",
        alignItems: "center",
        gap: 12,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 12,
        padding: 12,
        marginBottom: 8,
        backgroundColor: C.surface,
      },

      reportDatasetOptionActive: {
        borderColor: C.green,
        backgroundColor: C.mint2,
      },

      reportDatasetIcon: {
        width: 38,
        height: 38,
        borderRadius: 10,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: C.mint2,
      },

      reportDatasetName: {
        color: C.text,
        fontSize: 13,
        fontWeight: "800",
      },

      reportDatasetMeta: {
        color: C.muted,
        fontSize: 10,
        marginTop: 3,
      },

      reportDatasetRadio: {
        width: 20,
        height: 20,
        borderRadius: 10,
        borderWidth: 2,
        borderColor: C.border,
        alignItems: "center",
        justifyContent: "center",
      },

      reportDatasetRadioActive: {
        borderColor: C.green,
      },

      reportDatasetRadioInner: {
        width: 10,
        height: 10,
        borderRadius: 5,
        backgroundColor: C.green,
      },

      reportHeadingRow: {
        flexDirection: "row",
        alignItems: "center",
        gap: 12,
        marginBottom: 14,
      },

      reportStatusPill: {
        paddingHorizontal: 10,
        paddingVertical: 7,
        borderRadius: 999,
        backgroundColor: C.mint2,
      },

      reportStatusPillText: {
        color: C.greenDark,
        fontSize: 9,
        fontWeight: "800",
        letterSpacing: 0.8,
      },

      reportInsight: {
        marginTop: 12,
        borderRadius: 12,
        padding: 14,
        backgroundColor: C.mint2,
        borderWidth: 1,
        borderColor: C.border,
      },

      reportInsightLabel: {
        color: C.teal,
        fontSize: 9,
        fontWeight: "800",
        letterSpacing: 1.2,
        marginBottom: 5,
      },

      reportInsightTitle: {
        color: C.text,
        fontSize: 16,
        fontWeight: "800",
      },

      reportInsightText: {
        color: C.muted,
        fontSize: 12,
        lineHeight: 19,
        marginTop: 5,
      },

      chartRow: {
        flexDirection: "row",
        alignItems: "center",
        gap: 10,
        marginTop: 13,
      },

      chartLabel: {
        width: 100,
        color: C.text,
        fontSize: 11,
        fontWeight: "800",
      },

      chartTrack: {
        flex: 1,
        height: 12,
        borderRadius: 999,
        backgroundColor: C.mint2,
        overflow: "hidden",
      },

      chartBar: {
        height: "100%",
        borderRadius: 999,
      },

      chartValue: {
        width: 50,
        textAlign: "right",
        color: C.text,
        fontSize: 11,
        fontWeight: "800",
      },

      barChart: {
        alignItems: "flex-end",
        gap: 14,
        paddingTop: 20,
        paddingBottom: 8,
        paddingHorizontal: 8,
      },

      barColumn: {
        width: 54,
        alignItems: "center",
      },

      barValue: {
        color: C.muted,
        fontSize: 9,
        fontWeight: "800",
        marginBottom: 5,
      },

      barArea: {
        height: 180,
        width: 30,
        justifyContent: "flex-end",
        alignItems: "center",
      },

      verticalBar: {
        width: 24,
        borderTopLeftRadius: 6,
        borderTopRightRadius: 6,
      },

      barLabel: {
        color: C.text,
        fontSize: 10,
        fontWeight: "800",
        marginTop: 7,
      },

      recommendation: {
        color: C.text,
        fontSize: 14,
        lineHeight: 28,
      },

      exportRow: {
        flexDirection: "row",
        alignItems: "center",
        gap: 14,
        marginTop: 3,
      },

      pdfButton: {
        backgroundColor: C.teal,
      },

      exportHint: {
        color: C.muted,
        fontSize: 11,
        flex: 1,
      },

      profilePanel: {
        backgroundColor: C.surface,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 15,
        padding: 20,
      },

      profileName: {
        color: C.text,
        fontSize: 18,
        fontWeight: "800",
      },

      profileEmail: {
        color: C.muted,
        fontSize: 11,
        marginTop: 3,
      },

      profileIdentity: {
        flexDirection: "row",
        alignItems: "center",
        gap: 15,
        marginTop: 17,
        marginBottom: 20,
      },

      profileAvatar: {
        width: 65,
        height: 65,
        borderRadius: 17,
        backgroundColor: C.mint,
        alignItems: "center",
        justifyContent: "center",
      },

      profileAvatarText: {
        color: C.green,
        fontSize: 25,
        fontWeight: "800",
      },

      profileRole: {
        color: C.text,
        fontSize: 19,
        fontWeight: "800",
      },

      profileType: {
        color: C.text,
        fontSize: 13,
        marginTop: 4,
      },

      profileGrid: {
        flexDirection: "row",
        flexWrap: "wrap",
        gap: 12,
      },

      signOutButton: {
        alignSelf: "flex-start",
        height: 43,
        paddingHorizontal: 14,
        borderWidth: 1,
        borderColor: C.border,
        borderRadius: 9,
        flexDirection: "row",
        alignItems: "center",
        gap: 8,
        marginTop: 26,
      },

      signOutText: {
        color: C.danger,
        fontWeight: "800",
        fontSize: 13,
      },

      authThemeToggle: {
        flexDirection: "row",
        alignItems: "center",
        alignSelf: "center",
        gap: 7,
        paddingHorizontal: 13,
        paddingVertical: 8,
        borderRadius: 999,
        borderWidth: 1,
        borderColor: C.border,
        backgroundColor: C.surface,
        marginBottom: 14,
      },

      authThemeToggleText: {
        color: C.text,
        fontSize: 12,
        fontWeight: "700",
      },

      themeToggle: {
        height: 38,
        paddingHorizontal: 12,
        borderRadius: 10,
        borderWidth: 1,
        borderColor: C.border,
        backgroundColor: C.surface,
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
        marginLeft: "auto",
        marginRight: 12,
      },

      themeToggleText: {
        color: C.text,
        fontSize: 12,
        fontWeight: "800",
      },
    });
  }

  styles = createStyles();

  export { API };
