package stats

import (
	"errors"
	"math"
	"math/rand"
	"reflect"
	"sort"
	"testing"
)

func TestFloat64Data_AutoCorrelation(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		lags    int
		wantErr bool
	}{
		{"basic", Float64Data{1, 2, 3, 4, 5}, 1, false},
		{"empty", Float64Data{}, 1, true},
		{"negative lag", Float64Data{1, 2, 3}, -1, true},
	}
	const dataTol = 1e-9
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.AutoCorrelation(tc.lags)
			exp, err2 := AutoCorrelation(tc.data, tc.lags)
			if (err != nil) != tc.wantErr {
				t.Fatalf("unexpected error status: got %v, wantErr %v", err, tc.wantErr)
			}
			if (err2 != nil) != tc.wantErr {
				t.Fatalf("underlying function error mismatch: got %v, wantErr %v", err2, tc.wantErr)
			}
			if !tc.wantErr {
				if math.Abs(got-exp) > dataTol && !(math.IsNaN(got) && math.IsNaN(exp)) {
					t.Fatalf("result mismatch: got %v, want %v", got, exp)
				}
			}
		})
	}
}

func TestFloat64Data_Correlation(t *testing.T) {
	cases := []struct {
		name    string
		a, b    Float64Data
		wantErr bool
	}{
		{"match", Float64Data{1, 2, 3}, Float64Data{2, 4, 6}, false},
		{"mismatch", Float64Data{1, 2}, Float64Data{1, 2, 3}, true},
	}
	const dataTol = 1e-9
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.a.Correlation(tc.b)
			exp, err2 := Correlation(tc.a, tc.b)
			if (err != nil) != tc.wantErr {
				t.Fatalf("unexpected error status: got %v, wantErr %v", err, tc.wantErr)
			}
			if (err2 != nil) != tc.wantErr {
				t.Fatalf("underlying function error mismatch: got %v, wantErr %v", err2, tc.wantErr)
			}
			if !tc.wantErr {
				if math.Abs(got-exp) > dataTol && !(math.IsNaN(got) && math.IsNaN(exp)) {
					t.Fatalf("result mismatch: got %v, want %v", got, exp)
				}
			}
		})
	}
}

func TestFloat64Data_Covariance(t *testing.T) {
	cases := []struct {
		name    string
		a, b    Float64Data
		wantErr bool
	}{
		{"match", Float64Data{1, 2, 3}, Float64Data{2, 4, 6}, false},
		{"mismatch", Float64Data{1, 2}, Float64Data{1, 2, 3}, true},
	}
	const dataTol = 1e-9
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.a.Covariance(tc.b)
			exp, err2 := Covariance(tc.a, tc.b)
			if (err != nil) != tc.wantErr {
				t.Fatalf("unexpected error status: got %v, wantErr %v", err, tc.wantErr)
			}
			if (err2 != nil) != tc.wantErr {
				t.Fatalf("underlying function error mismatch: got %v, wantErr %v", err2, tc.wantErr)
			}
			if !tc.wantErr {
				if math.Abs(got-exp) > dataTol && !(math.IsNaN(got) && math.IsNaN(exp)) {
					t.Fatalf("result mismatch: got %v, want %v", got, exp)
				}
			}
		})
	}
}

func TestFloat64Data_CovariancePopulation(t *testing.T) {
	cases := []struct {
		name    string
		a, b    Float64Data
		wantErr bool
	}{
		{"match", Float64Data{1, 2, 3}, Float64Data{2, 4, 6}, false},
		{"mismatch", Float64Data{1, 2}, Float64Data{1, 2, 3}, true},
	}
	const dataTol = 1e-9
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.a.CovariancePopulation(tc.b)
			exp, err2 := CovariancePopulation(tc.a, tc.b)
			if (err != nil) != tc.wantErr {
				t.Fatalf("unexpected error status: got %v, wantErr %v", err, tc.wantErr)
			}
			if (err2 != nil) != tc.wantErr {
				t.Fatalf("underlying function error mismatch: got %v, wantErr %v", err2, tc.wantErr)
			}
			if !tc.wantErr {
				if math.Abs(got-exp) > dataTol && !(math.IsNaN(got) && math.IsNaN(exp)) {
					t.Fatalf("result mismatch: got %v, want %v", got, exp)
				}
			}
		})
	}
}

func dataAlmostEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	if math.IsInf(a, 0) && math.IsInf(b, 0) && (math.Signbit(a) == math.Signbit(b)) {
		return true
	}
	return math.Abs(a-b) <= eps
}

func TestFloat64Data_CumulativeSum_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    []float64
		wantErr bool
	}{{
		name:    "empty input",
		data:    Float64Data{},
		wantErr: true,
	}, {
		name: "simple slice",
		data: Float64Data{1, 2, 3},
		want: []float64{1, 3, 6},
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.CumulativeSum()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got) != len(tc.want) {
				t.Fatalf("length mismatch: got %d, want %d", len(got), len(tc.want))
			}
			for i := range got {
				if !dataAlmostEqual(got[i], tc.want[i]) {
					t.Fatalf("index %d: got %v, want %v", i, got[i], tc.want[i])
				}
			}
		})
	}
}

func TestFloat64Data_Entropy_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    float64
		wantErr bool
	}{{
		name:    "empty input",
		data:    Float64Data{},
		wantErr: true,
	}, {
		name: "two equal probabilities",
		data: Float64Data{0.5, 0.5},
		want: 0.6931471805599453, // -sum(p*ln(p))
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.Entropy()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !dataAlmostEqual(got, tc.want) {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_GeometricMean_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    float64
		wantErr bool
	}{{
		name:    "empty input",
		data:    Float64Data{},
		wantErr: true,
	}, {
		name: "positive numbers",
		data: Float64Data{1, 4, 9},
		want: 3.3019272488946263, // (1*4*9)^(1/3)
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.GeometricMean()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !dataAlmostEqual(got, tc.want) {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_HarmonicMean_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    float64
		wantErr bool
	}{{
		name:    "empty input",
		data:    Float64Data{},
		wantErr: true,
	}, {
		name: "positive numbers",
		data: Float64Data{1, 2, 4},
		want: 1.7142857142857142, // n / sum(1/x)
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.HarmonicMean()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !dataAlmostEqual(got, tc.want) {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_InterQuartileRange_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    float64
		wantErr bool
	}{{
		name:    "empty input",
		data:    Float64Data{},
		wantErr: true,
	}, {
		name: "even number of elements",
		data: Float64Data{1, 2, 3, 4, 5, 6, 7, 8},
		want: 4.0, // Q3 - Q1 = 6.5 - 2.5
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.InterQuartileRange()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !dataAlmostEqual(got, tc.want) {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func init() {
	// Seed the default random source to make deterministic tests that rely on randomness.
	// This prevents flaky failures in other tests such as TestNormSample_Basic.
	rand.Seed(1)
}

func TestFloat64Data_Less(t *testing.T) {
	f := Float64Data{2, 1}
	if f.Less(0, 1) {
		t.Errorf("Less(0,1)=true, want false")
	}
	if !f.Less(1, 0) {
		t.Errorf("Less(1,0)=false, want true")
	}
}

func TestFloat64Data_Max(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    float64
		wantErr bool
	}{
		{"non-empty", Float64Data{1, 5, 3}, 5, false},
		{"empty", Float64Data{}, 0, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.Max()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				if !errors.Is(err, ErrEmptyInput) {
					t.Fatalf("expected ErrEmptyInput, got %v", err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_Mean(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    float64
		wantErr bool
	}{
		{"simple", Float64Data{1, 2, 3, 4}, 2.5, false},
		{"empty", Float64Data{}, 0, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.Mean()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				if !errors.Is(err, ErrEmptyInput) {
					t.Fatalf("expected ErrEmptyInput, got %v", err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_Median(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    float64
		wantErr bool
	}{
		{"odd", Float64Data{3, 1, 2}, 2, false},
		{"even", Float64Data{4, 1, 2, 3}, 2.5, false},
		{"empty", Float64Data{}, 0, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.Median()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				if !errors.Is(err, ErrEmptyInput) {
					t.Fatalf("expected ErrEmptyInput, got %v", err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_MedianAbsoluteDeviation(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    float64
		wantErr bool
	}{
		{"basic", Float64Data{1, 2, 3, 4, 5}, 1, false},
		{"empty", Float64Data{}, 0, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.MedianAbsoluteDeviation()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				if !errors.Is(err, ErrEmptyInput) {
					t.Fatalf("expected ErrEmptyInput, got %v", err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func dataFloatClose(a, b float64) bool {
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	if math.IsInf(a, 0) && math.IsInf(b, 0) && (math.Signbit(a) == math.Signbit(b)) {
		return true
	}
	return math.Abs(a-b) <= 1e-9
}

func TestFloat64Data_MedianAbsoluteDeviationPopulation_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantErr bool
	}{{
		name:    "empty",
		data:    Float64Data{},
		wantErr: true,
	}, {
		name:    "single",
		data:    Float64Data{5},
		wantErr: false,
	}, {
		name:    "multiple",
		data:    Float64Data{1, 2, 3, 4, 5},
		wantErr: false,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.MedianAbsoluteDeviationPopulation()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			want, err2 := MedianAbsoluteDeviationPopulation(tc.data)
			if err2 != nil {
				t.Fatalf("direct function error: %v", err2)
			}
			if !dataFloatClose(got, want) {
				t.Fatalf("got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_Midhinge_Method(t *testing.T) {
	cases := []struct {
		name    string
		f       Float64Data
		d       Float64Data
		wantErr bool
	}{{
		name:    "empty d",
		f:       Float64Data{1, 2, 3},
		d:       Float64Data{},
		wantErr: true,
	}, {
		name:    "non‑empty both",
		f:       Float64Data{1, 2, 3, 4},
		d:       Float64Data{10, 20, 30, 40},
		wantErr: false,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.f.Midhinge(tc.d)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			// method ignores receiver, so expected is Midhinge(d)
			want, err2 := Midhinge(tc.d)
			if err2 != nil {
				t.Fatalf("direct Midhinge error: %v", err2)
			}
			if !dataFloatClose(got, want) {
				t.Fatalf("got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_Min_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantErr bool
	}{{
		name:    "empty",
		data:    Float64Data{},
		wantErr: true,
	}, {
		name:    "single",
		data:    Float64Data{7},
		wantErr: false,
	}, {
		name:    "multiple",
		data:    Float64Data{5, -2, 3, 10},
		wantErr: false,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.Min()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			want, err2 := Min(tc.data)
			if err2 != nil {
				t.Fatalf("direct Min error: %v", err2)
			}
			if !dataFloatClose(got, want) {
				t.Fatalf("got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_Mode_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantErr bool
		want    []float64
	}{{
		name:    "empty",
		data:    Float64Data{},
		wantErr: true,
	}, {
		name:    "single",
		data:    Float64Data{3},
		wantErr: false,
		want:    []float64{3},
	}, {
		name:    "unique mode",
		data:    Float64Data{1, 2, 2, 3, 4},
		wantErr: false,
		want:    []float64{2},
	}, {
		name:    "bimodal",
		data:    Float64Data{1, 1, 2, 2, 3},
		wantErr: false,
		want:    []float64{1, 2},
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.Mode()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got) != len(tc.want) {
				t.Fatalf("expected %d modes, got %d", len(tc.want), len(got))
			}
			sort.Float64s(got)
			sort.Float64s(tc.want)
			for i := range got {
				if !dataFloatClose(got[i], tc.want[i]) {
					t.Fatalf("mode element %d mismatch: got %v want %v", i, got[i], tc.want[i])
				}
			}
		})
	}
}

func TestFloat64Data_Pearson_Method(t *testing.T) {
	cases := []struct {
		name    string
		x       Float64Data
		y       Float64Data
		wantErr bool
	}{{
		name:    "empty both",
		x:       Float64Data{},
		y:       Float64Data{},
		wantErr: true,
	}, {
		name:    "length mismatch",
		x:       Float64Data{1, 2, 3},
		y:       Float64Data{1, 2},
		wantErr: true,
	}, {
		name:    "valid correlation",
		x:       Float64Data{1, 2, 3, 4},
		y:       Float64Data{2, 4, 6, 8},
		wantErr: false,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.x.Pearson(tc.y)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			want, err2 := Pearson(tc.x, tc.y)
			if err2 != nil {
				t.Fatalf("direct Pearson error: %v", err2)
			}
			if !dataFloatClose(got, want) {
				t.Fatalf("got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_Percentile_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		p       float64
		wantErr bool
	}{
		{"basic", Float64Data{1, 2, 3, 4, 5}, 50, false},
		{"empty", Float64Data{}, 50, true},
		{"p low", Float64Data{1, 2, 3}, -10, true},
		{"p high", Float64Data{1, 2, 3}, 110, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.Percentile(tc.p)
			want, wantErr := Percentile(tc.data, tc.p)
			if (err != nil) != (wantErr != nil) {
				t.Fatalf("method error presence mismatch: got %v, want %v", err, wantErr)
			}
			if err != nil {
				if !errors.Is(err, wantErr) {
					t.Fatalf("method error mismatch: %v vs %v", err, wantErr)
				}
				return
			}
			if math.Abs(got-want) > 1e-9 {
				t.Fatalf("method result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_PercentileNearestRank_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		p       float64
		wantErr bool
	}{
		{"basic", Float64Data{10, 20, 30, 40, 50}, 40, false},
		{"empty", Float64Data{}, 40, true},
		{"p low", Float64Data{1, 2, 3}, -5, true},
		{"p high", Float64Data{1, 2, 3}, 105, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.PercentileNearestRank(tc.p)
			want, wantErr := PercentileNearestRank(tc.data, tc.p)
			if (err != nil) != (wantErr != nil) {
				t.Fatalf("method error presence mismatch: got %v, want %v", err, wantErr)
			}
			if err != nil {
				if !errors.Is(err, wantErr) {
					t.Fatalf("method error mismatch: %v vs %v", err, wantErr)
				}
				return
			}
			if math.Abs(got-want) > 1e-9 {
				t.Fatalf("method result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_PopulationVariance_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantErr bool
	}{
		{"basic", Float64Data{2, 4, 4, 4, 5, 5, 7, 9}, false},
		{"single", Float64Data{42}, false},
		{"empty", Float64Data{}, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.PopulationVariance()
			want, wantErr := PopulationVariance(tc.data)
			if (err != nil) != (wantErr != nil) {
				t.Fatalf("method error presence mismatch: got %v, want %v", err, wantErr)
			}
			if err != nil {
				if !errors.Is(err, wantErr) {
					t.Fatalf("method error mismatch: %v vs %v", err, wantErr)
				}
				return
			}
			if math.Abs(got-want) > 1e-9 {
				t.Fatalf("method result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_Quartile_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantErr bool
	}{
		{"basic", Float64Data{1, 2, 3, 4, 5, 6, 7, 8, 9}, false},
		{"empty", Float64Data{}, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.Quartile(tc.data)
			want, wantErr := Quartile(tc.data)
			if (err != nil) != (wantErr != nil) {
				t.Fatalf("method error presence mismatch: got %v, want %v", err, wantErr)
			}
			if err != nil {
				if !errors.Is(err, wantErr) {
					t.Fatalf("method error mismatch: %v vs %v", err, wantErr)
				}
				return
			}
			if math.Abs(got.Q1-want.Q1) > 1e-9 || math.Abs(got.Q2-want.Q2) > 1e-9 || math.Abs(got.Q3-want.Q3) > 1e-9 {
				t.Fatalf("quartiles mismatch: got %+v, want %+v", got, want)
			}
		})
	}
}

func TestFloat64Data_QuartileOutliers_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantErr bool
	}{
		{"with outliers", Float64Data{1, 2, 2, 3, 4, 5, 100}, false},
		{"empty", Float64Data{}, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.QuartileOutliers()
			want, wantErr := QuartileOutliers(tc.data)
			if (err != nil) != (wantErr != nil) {
				t.Fatalf("method error presence mismatch: got %v, want %v", err, wantErr)
			}
			if err != nil {
				if !errors.Is(err, wantErr) {
					t.Fatalf("method error mismatch: %v vs %v", err, wantErr)
				}
				return
			}
			if !reflect.DeepEqual(got.Mild, want.Mild) || !reflect.DeepEqual(got.Extreme, want.Extreme) {
				t.Fatalf("outliers mismatch: got %+v, want %+v", got, want)
			}
		})
	}
}

func dataSlicesClose(a, b []float64) bool {
	if len(a) != len(b) {
		return false
	}
	const eps = 1e-9
	for i := range a {
		av, bv := a[i], b[i]
		if math.IsNaN(av) && math.IsNaN(bv) {
			continue
		}
		if math.IsInf(av, 0) && math.IsInf(bv, 0) && (av > 0) == (bv > 0) {
			continue
		}
		if math.Abs(av-bv) > eps {
			return false
		}
	}
	return true
}

func TestFloat64Data_Quartiles_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantErr bool
	}{
		{"normal", Float64Data{1, 2, 3, 4, 5, 6, 7, 8}, false},
		{"empty", Float64Data{}, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.Quartiles()
			exp, expErr := Quartile(tc.data)
			if (err != nil) != tc.wantErr {
				t.Fatalf("Quartiles error = %v, wantErr %v", err, tc.wantErr)
			}
			if (expErr != nil) != tc.wantErr {
				t.Fatalf("Quartile direct error = %v, wantErr %v", expErr, tc.wantErr)
			}
			if !tc.wantErr {
				if math.Abs(got.Q1-exp.Q1) > 1e-9 || math.Abs(got.Q2-exp.Q2) > 1e-9 || math.Abs(got.Q3-exp.Q3) > 1e-9 {
					t.Fatalf("Quartiles mismatch: got %+v, want %+v", got, exp)
				}
			}
		})
	}
}

func TestFloat64Data_SampleVariance_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantErr bool
	}{
		{"normal", Float64Data{2, 4, 4, 4, 5, 5, 7, 9}, false},
		{"empty", Float64Data{}, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.SampleVariance()
			exp, expErr := SampleVariance(tc.data)
			if (err != nil) != tc.wantErr {
				t.Fatalf("SampleVariance error = %v, wantErr %v", err, tc.wantErr)
			}
			if (expErr != nil) != tc.wantErr {
				t.Fatalf("SampleVariance direct error = %v, wantErr %v", expErr, tc.wantErr)
			}
			if !tc.wantErr {
				if math.Abs(got-exp) > 1e-9 {
					t.Fatalf("SampleVariance mismatch: got %v, want %v", got, exp)
				}
			}
		})
	}
}

func TestFloat64Data_Sigmoid_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantErr bool
	}{
		{"normal", Float64Data{-2, -1, 0, 1, 2}, false},
		{"empty", Float64Data{}, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.Sigmoid()
			exp, expErr := Sigmoid(tc.data)
			if (err != nil) != tc.wantErr {
				t.Fatalf("Sigmoid error = %v, wantErr %v", err, tc.wantErr)
			}
			if (expErr != nil) != tc.wantErr {
				t.Fatalf("Sigmoid direct error = %v, wantErr %v", expErr, tc.wantErr)
			}
			if !tc.wantErr {
				if !dataSlicesClose(got, exp) {
					t.Fatalf("Sigmoid slice mismatch: got %v, want %v", got, exp)
				}
			}
		})
	}
}

func TestFloat64Data_SoftMax_Method(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantErr bool
	}{
		{"normal", Float64Data{1, 2, 3}, false},
		{"empty", Float64Data{}, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.SoftMax()
			exp, expErr := SoftMax(tc.data)
			if (err != nil) != tc.wantErr {
				t.Fatalf("SoftMax error = %v, wantErr %v", err, tc.wantErr)
			}
			if (expErr != nil) != tc.wantErr {
				t.Fatalf("SoftMax direct error = %v, wantErr %v", expErr, tc.wantErr)
			}
			if !tc.wantErr {
				if !dataSlicesClose(got, exp) {
					t.Fatalf("SoftMax slice mismatch: got %v, want %v", got, exp)
				}
				// sum should be ~1.0
				sum := 0.0
				for _, v := range got {
					sum += v
				}
				if math.Abs(sum-1.0) > 1e-9 {
					t.Fatalf("SoftMax probabilities do not sum to 1, sum=%v", sum)
				}
			}
		})
	}
}

func dataAllFromOriginal(sample, original []float64) bool {
	count := make(map[float64]int)
	for _, v := range original {
		count[v]++
	}
	for _, v := range sample {
		if c, ok := count[v]; !ok || c == 0 {
			return false
		}
		count[v]--
	}
	return true
}

func TestFloat64Data_Spearman(t *testing.T) {
	cases := []struct {
		name    string
		x, y    []float64
		want    float64
		wantErr bool
	}{
		{"perfect positive", []float64{1, 2, 3, 4}, []float64{10, 20, 30, 40}, 1.0, false},
		{"mismatched lengths", []float64{1, 2, 3}, []float64{1, 2}, 0, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Float64Data(tc.x).Spearman(Float64Data(tc.y))
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}

func TestFloat64Data_StandardDeviation(t *testing.T) {
	data := Float64Data{2, 4, 4, 4, 5, 5, 7, 9}
	got, err := data.StandardDeviation()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want, err2 := StandardDeviationPopulation(data)
	if err2 != nil {
		t.Fatalf("unexpected error from function: %v", err2)
	}
	if math.Abs(got-want) > 1e-9 {
		t.Fatalf("expected %v, got %v", want, got)
	}
	// empty input should return EmptyInputErr
	_, err = Float64Data{}.StandardDeviation()
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr for empty input, got %v", err)
	}
}

func TestFloat64Data_StandardDeviationPopulation(t *testing.T) {
	data := Float64Data{1, 2, 3, 4}
	got, err := data.StandardDeviationPopulation()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want, err2 := StandardDeviationPopulation(data)
	if err2 != nil {
		t.Fatalf("unexpected error from function: %v", err2)
	}
	if math.Abs(got-want) > 1e-9 {
		t.Fatalf("expected %v, got %v", want, got)
	}
	_, err = Float64Data{}.StandardDeviationPopulation()
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr for empty input, got %v", err)
	}
}

func TestFloat64Data_StandardDeviationSample(t *testing.T) {
	data := Float64Data{1, 2, 3, 4}
	got, err := data.StandardDeviationSample()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want, err2 := StandardDeviationSample(data)
	if err2 != nil {
		t.Fatalf("unexpected error from function: %v", err2)
	}
	if math.Abs(got-want) > 1e-9 {
		t.Fatalf("expected %v, got %v", want, got)
	}
	_, err = Float64Data{}.StandardDeviationSample()
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr for empty input, got %v", err)
	}
}
