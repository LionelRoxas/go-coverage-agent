package stats

import (
	"errors"
	"math"
	"reflect"
	"sort"
	"testing"
)

func dataSlicesClose(a, b []float64) bool {
	if len(a) != len(b) {
		return false
	}
	const eps = 1e-9
	for i := range a {
		if math.IsNaN(a[i]) && math.IsNaN(b[i]) {
			continue
		}
		if math.Abs(a[i]-b[i]) > eps {
			return false
		}
	}
	return true
}

func TestFloat64Data_AutoCorrelation(t *testing.T) {
	cases := []struct {
		name string
		data []float64
		lags int
	}{
		{"basic", []float64{1, 2, 3, 4, 5}, 1},
		{"zero lag", []float64{1, 2, 3, 4, 5}, 0},
		{"empty", []float64{}, 0},
		{"negative lag", []float64{1, 2, 3}, -1},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			f := Float64Data(tc.data)
			got, err := f.AutoCorrelation(tc.lags)
			want, wantErr := AutoCorrelation(f, tc.lags)
			if (err != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", err, wantErr)
			}
			if err != nil && wantErr != nil && !errors.Is(err, wantErr) {
				t.Fatalf("error type mismatch: got %v, want %v", err, wantErr)
			}
			if math.IsNaN(got) && math.IsNaN(want) {
				return
			}
			if math.Abs(got-want) > 1e-9 {
				t.Fatalf("result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_Correlation(t *testing.T) {
	cases := []struct {
		name string
		a    []float64
		b    []float64
	}{
		{"matching", []float64{1, 2, 3, 4}, []float64{2, 4, 6, 8}},
		{"mismatched length", []float64{1, 2, 3}, []float64{1, 2}},
		{"empty", []float64{}, []float64{}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			f := Float64Data(tc.a)
			d := Float64Data(tc.b)
			got, err := f.Correlation(d)
			want, wantErr := Correlation(f, d)
			if (err != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", err, wantErr)
			}
			if err != nil && wantErr != nil && !errors.Is(err, wantErr) {
				t.Fatalf("error type mismatch: got %v, want %v", err, wantErr)
			}
			if math.IsNaN(got) && math.IsNaN(want) {
				return
			}
			if math.Abs(got-want) > 1e-9 {
				t.Fatalf("result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_Covariance(t *testing.T) {
	cases := []struct {
		name string
		a    []float64
		b    []float64
	}{
		{"matching", []float64{1, 2, 3}, []float64{2, 4, 6}},
		{"mismatched length", []float64{1, 2}, []float64{1, 2, 3}},
		{"empty", []float64{}, []float64{}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			f := Float64Data(tc.a)
			d := Float64Data(tc.b)
			got, err := f.Covariance(d)
			want, wantErr := Covariance(f, d)
			if (err != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", err, wantErr)
			}
			if err != nil && wantErr != nil && !errors.Is(err, wantErr) {
				t.Fatalf("error type mismatch: got %v, want %v", err, wantErr)
			}
			if math.IsNaN(got) && math.IsNaN(want) {
				return
			}
			if math.Abs(got-want) > 1e-9 {
				t.Fatalf("result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_CovariancePopulation(t *testing.T) {
	cases := []struct {
		name string
		a    []float64
		b    []float64
	}{
		{"matching", []float64{1, 2, 3, 4}, []float64{2, 4, 6, 8}},
		{"mismatched length", []float64{1, 2, 3}, []float64{1, 2}},
		{"empty", []float64{}, []float64{}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			f := Float64Data(tc.a)
			d := Float64Data(tc.b)
			got, err := f.CovariancePopulation(d)
			want, wantErr := CovariancePopulation(f, d)
			if (err != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", err, wantErr)
			}
			if err != nil && wantErr != nil && !errors.Is(err, wantErr) {
				t.Fatalf("error type mismatch: got %v, want %v", err, wantErr)
			}
			if math.IsNaN(got) && math.IsNaN(want) {
				return
			}
			if math.Abs(got-want) > 1e-9 {
				t.Fatalf("result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_CumulativeSum(t *testing.T) {
	cases := []struct {
		name string
		data []float64
	}{
		{"normal", []float64{1, 2, 3, 4}},
		{"empty", []float64{}},
		{"nil", nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			f := Float64Data(tc.data)
			got, err := f.CumulativeSum()
			want, wantErr := CumulativeSum(f)
			if (err != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", err, wantErr)
			}
			if err != nil && wantErr != nil && !errors.Is(err, wantErr) {
				t.Fatalf("error type mismatch: got %v, want %v", err, wantErr)
			}
			if !dataSlicesClose(got, want) {
				t.Fatalf("slice mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_Entropy(t *testing.T) {
	cases := []struct {
		name string
		data Float64Data
	}{
		{"empty", Float64Data{}},
		{"single", Float64Data{0.5}},
		{"multiple", Float64Data{0.1, 0.2, 0.7}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, gotErr := tc.data.Entropy()
			want, wantErr := Entropy(tc.data)
			if (gotErr != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", gotErr, wantErr)
			}
			if gotErr == nil && math.Abs(got-want) > 1e-9 {
				t.Errorf("result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_GeometricMean(t *testing.T) {
	cases := []struct {
		name string
		data Float64Data
	}{
		{"empty", Float64Data{}},
		{"positive", Float64Data{1, 2, 3, 4}},
		{"contains zero", Float64Data{0, 2, 5}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, gotErr := tc.data.GeometricMean()
			want, wantErr := GeometricMean(tc.data)
			if (gotErr != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", gotErr, wantErr)
			}
			if gotErr == nil && math.Abs(got-want) > 1e-9 {
				t.Errorf("result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_HarmonicMean(t *testing.T) {
	cases := []struct {
		name string
		data Float64Data
	}{
		{"empty", Float64Data{}},
		{"positive", Float64Data{1, 2, 4}},
		{"contains zero", Float64Data{0, 5, 10}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, gotErr := tc.data.HarmonicMean()
			want, wantErr := HarmonicMean(tc.data)
			if (gotErr != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", gotErr, wantErr)
			}
			if gotErr == nil && math.Abs(got-want) > 1e-9 {
				t.Errorf("result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_InterQuartileRange(t *testing.T) {
	cases := []struct {
		name string
		data Float64Data
	}{
		{"empty", Float64Data{}},
		{"odd", Float64Data{1, 2, 3, 4, 5}},
		{"even", Float64Data{10, 20, 30, 40}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, gotErr := tc.data.InterQuartileRange()
			want, wantErr := InterQuartileRange(tc.data)
			if (gotErr != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", gotErr, wantErr)
			}
			if gotErr == nil && math.Abs(got-want) > 1e-9 {
				t.Errorf("result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_Less(t *testing.T) {
	data := Float64Data{5, 3, 8}
	cases := []struct {
		name string
		i, j int
	}{
		{"first less second", 1, 0},
		{"second less third", 0, 2},
		{"equal indices", 2, 2},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := data.Less(tc.i, tc.j)
			want := data[tc.i] < data[tc.j]
			if got != want {
				t.Errorf("Less(%d,%d) = %v, want %v", tc.i, tc.j, got, want)
			}
		})
	}
}

func TestFloat64Data_Max(t *testing.T) {
	cases := []struct {
		name    string
		data    []float64
		want    float64
		wantErr bool
	}{
		{"empty", []float64{}, 0, true},
		{"single", []float64{5}, 5, false},
		{"multiple", []float64{1, 3, 2, 7, 5}, 7, false},
		{"negative", []float64{-2, -5, -1}, -1, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Float64Data(tc.data).Max()
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
			if got != tc.want {
				t.Errorf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_Mean(t *testing.T) {
	cases := []struct {
		name    string
		data    []float64
		want    float64
		wantErr bool
	}{
		{"empty", []float64{}, 0, true},
		{"single", []float64{4}, 4, false},
		{"multiple", []float64{1, 2, 3, 4}, 2.5, false},
		{"negative", []float64{-2, -4, -6}, -4, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Float64Data(tc.data).Mean()
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
				t.Errorf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_Median(t *testing.T) {
	cases := []struct {
		name    string
		data    []float64
		want    float64
		wantErr bool
	}{
		{"empty", []float64{}, 0, true},
		{"odd", []float64{5, 1, 3}, 3, false},
		{"even", []float64{4, 2, 1, 3}, 2.5, false},
		{"unsorted", []float64{10, -2, 7, 3}, 5, false}, // median of [-2,3,7,10] => (3+7)/2 =5
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Float64Data(tc.data).Median()
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
				t.Errorf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_MedianAbsoluteDeviation(t *testing.T) {
	cases := []struct {
		name    string
		data    []float64
		want    float64
		wantErr bool
	}{
		{"empty", []float64{}, 0, true},
		{"single", []float64{8}, 0, false},
		{"simple", []float64{1, 2, 3, 4, 5}, 1, false}, // median 3, deviations [2,1,0,1,2] median 1
		{"even", []float64{1, 2, 3, 4}, 1, false},      // median 2.5, deviations [1.5,0.5,0.5,1.5] median 1
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Float64Data(tc.data).MedianAbsoluteDeviation()
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
				t.Errorf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_MedianAbsoluteDeviationPopulation(t *testing.T) {
	cases := []struct {
		name    string
		data    []float64
		want    float64
		wantErr bool
	}{
		{"empty", []float64{}, 0, true},
		{"single", []float64{8}, 0, false},
		{"simple", []float64{1, 2, 3, 4, 5}, 1, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Float64Data(tc.data).MedianAbsoluteDeviationPopulation()
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
				t.Errorf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func dataFloatEqual(got, want float64) bool {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= eps
}

func TestFloat64Data_Min(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    float64
		wantErr bool
	}{
		{"empty", Float64Data{}, 0, true},
		{"single", Float64Data{42.0}, 42.0, false},
		{"multiple", Float64Data{5.5, -2.3, 7.1, -2.3}, -2.3, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.Min()
			if tc.wantErr {
				if err == nil {
					t.Errorf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !dataFloatEqual(got, tc.want) {
				t.Errorf("Min() = %v, want %v", got, tc.want)
			}
			// compare with package function
			direct, err2 := Min(tc.data)
			if err2 != nil {
				t.Fatalf("direct Min returned error: %v", err2)
			}
			if !dataFloatEqual(direct, got) {
				t.Errorf("method Min result %v differs from direct Min %v", got, direct)
			}
		})
	}
}

func TestFloat64Data_Midhinge(t *testing.T) {
	cases := []struct {
		name    string
		recv    Float64Data // receiver is ignored by the method
		arg     Float64Data
		want    float64
		wantErr bool
	}{
		{"empty", Float64Data{}, Float64Data{}, 0, true},
		{"basic", Float64Data{}, Float64Data{1, 2, 3, 4, 5, 6, 7, 8}, 4.5, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.recv.Midhinge(tc.arg)
			if tc.wantErr {
				if err == nil {
					t.Errorf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !dataFloatEqual(got, tc.want) {
				t.Errorf("Midhinge() = %v, want %v", got, tc.want)
			}
			direct, err2 := Midhinge(tc.arg)
			if err2 != nil {
				t.Fatalf("direct Midhinge returned error: %v", err2)
			}
			if !dataFloatEqual(direct, got) {
				t.Errorf("method Midhinge result %v differs from direct Midhinge %v", got, direct)
			}
		})
	}
}

func TestFloat64Data_Mode(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    []float64
		wantErr bool
	}{
		{"empty", Float64Data{}, nil, true},
		{"single mode", Float64Data{1, 2, 2, 3, 4}, []float64{2}, false},
		{"multiple modes", Float64Data{1, 1, 2, 2, 3}, []float64{1, 2}, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.Mode()
			if tc.wantErr {
				if err == nil {
					t.Errorf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got) != len(tc.want) {
				t.Errorf("Mode length = %d, want %d", len(got), len(tc.want))
			}
			// compare values (order not guaranteed, sort both)
			sort.Float64s(got)
			sort.Float64s(tc.want)
			for i := range got {
				if !dataFloatEqual(got[i], tc.want[i]) {
					t.Errorf("Mode[%d] = %v, want %v", i, got[i], tc.want[i])
				}
			}
			direct, err2 := Mode(tc.data)
			if err2 != nil {
				t.Fatalf("direct Mode returned error: %v", err2)
			}
			sort.Float64s(direct)
			if len(direct) != len(got) {
				t.Errorf("method Mode length %d differs from direct Mode length %d", len(got), len(direct))
			}
			for i := range direct {
				if !dataFloatEqual(direct[i], got[i]) {
					t.Errorf("method Mode element %v differs from direct Mode element %v", got[i], direct[i])
				}
			}
		})
	}
}

func TestFloat64Data_Percentile(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		p       float64
		want    float64
		wantErr bool
	}{
		{"empty", Float64Data{}, 50, 0, true},
		{"median", Float64Data{1, 3, 5, 7, 9}, 50, 5, false},
		{"lower quartile", Float64Data{1, 2, 3, 4, 5, 6, 7, 8}, 25, 2.75, false},
		{"upper quartile", Float64Data{1, 2, 3, 4, 5, 6, 7, 8}, 75, 6.25, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.Percentile(tc.p)
			if tc.wantErr {
				if err == nil {
					t.Errorf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !dataFloatEqual(got, tc.want) {
				t.Errorf("Percentile(%v) = %v, want %v", tc.p, got, tc.want)
			}
			direct, err2 := Percentile(tc.data, tc.p)
			if err2 != nil {
				t.Fatalf("direct Percentile returned error: %v", err2)
			}
			if !dataFloatEqual(direct, got) {
				t.Errorf("method Percentile result %v differs from direct Percentile %v", got, direct)
			}
		})
	}
}

func dataFloatClose(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	return math.Abs(a-b) <= eps
}

func TestFloat64Data_Pearson(t *testing.T) {
	cases := []struct {
		name    string
		x, y    Float64Data
		want    float64
		wantErr bool
	}{
		{"positive", Float64Data{1, 2, 3}, Float64Data{1, 2, 3}, 1, false},
		{"negative", Float64Data{1, 2, 3}, Float64Data{3, 2, 1}, -1, false},
		{"mismatch", Float64Data{1, 2, 3}, Float64Data{1, 2}, 0, true},
	}
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
			if !dataFloatClose(got, tc.want) {
				t.Errorf("Pearson = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_PercentileNearestRank(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		p       float64
		want    float64
		wantErr bool
	}{
		{"basic", Float64Data{1, 2, 3, 4, 5}, 40, 2, false},
		{"empty", Float64Data{}, 50, 0, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.PercentileNearestRank(tc.p)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !dataFloatClose(got, tc.want) {
				t.Errorf("PercentileNearestRank = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_PopulationVariance(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    float64
		wantErr bool
	}{
		{"basic", Float64Data{1, 2, 3, 4}, 1.25, false},
		{"empty", Float64Data{}, 0, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.PopulationVariance()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !dataFloatClose(got, tc.want) {
				t.Errorf("PopulationVariance = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_Quartile(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    Quartiles
		wantErr bool
	}{
		{"basic", Float64Data{1, 2, 3, 4, 5, 6, 7, 8}, Quartiles{Q1: 2.5, Q2: 4.5, Q3: 6.5}, false},
		{"empty", Float64Data{}, Quartiles{}, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.Quartile(tc.data)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !dataFloatClose(got.Q1, tc.want.Q1) || !dataFloatClose(got.Q2, tc.want.Q2) || !dataFloatClose(got.Q3, tc.want.Q3) {
				t.Errorf("Quartile = %+v, want %+v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_QuartileOutliers(t *testing.T) {
	cases := []struct {
		name        string
		data        Float64Data
		wantMild    Float64Data
		wantExtreme Float64Data
		wantErr     bool
	}{
		{"extreme", Float64Data{1, 2, 3, 4, 5, 100}, Float64Data{}, Float64Data{100}, false},
		{"none", Float64Data{10, 12, 13, 14, 15}, Float64Data{}, Float64Data{}, false},
		{"empty", Float64Data{}, Float64Data{}, Float64Data{}, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.QuartileOutliers()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got.Mild) != len(tc.wantMild) {
				t.Errorf("Mild length = %d, want %d", len(got.Mild), len(tc.wantMild))
			} else {
				for i, v := range got.Mild {
					if !dataFloatClose(v, tc.wantMild[i]) {
						t.Errorf("Mild[%d] = %v, want %v", i, v, tc.wantMild[i])
					}
				}
			}
			if len(got.Extreme) != len(tc.wantExtreme) {
				t.Errorf("Extreme length = %d, want %d", len(got.Extreme), len(tc.wantExtreme))
			} else {
				for i, v := range got.Extreme {
					if !dataFloatClose(v, tc.wantExtreme[i]) {
						t.Errorf("Extreme[%d] = %v, want %v", i, v, tc.wantExtreme[i])
					}
				}
			}
		})
	}
}

func dataAllInSet(sample []float64, set Float64Data) bool {
	m := make(map[float64]struct{}, len(set))
	for _, v := range set {
		m[v] = struct{}{}
	}
	for _, v := range sample {
		if _, ok := m[v]; !ok {
			return false
		}
	}
	return true
}

func TestFloat64Data_Quartiles(t *testing.T) {
	cases := []struct {
		name string
		data Float64Data
	}{
		{"normal", Float64Data{1, 2, 3, 4, 5, 6, 7, 8}},
		{"empty", Float64Data{}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, errGot := tc.data.Quartiles()
			want, errWant := Quartile(tc.data)
			if (errGot != nil) != (errWant != nil) {
				t.Fatalf("error mismatch: got %v, want %v", errGot, errWant)
			}
			if errGot != nil {
				return
			}
			if !reflect.DeepEqual(got, want) {
				t.Errorf("Quartiles mismatch: got %+v, want %+v", got, want)
			}
		})
	}
}

func TestFloat64Data_Sample(t *testing.T) {
	orig := Float64Data{1, 2, 3}
	cases := []struct {
		name      string
		n         int
		replace   bool
		expectErr bool
	}{
		{"with replacement", 5, true, false},
		{"without replacement ok", 2, false, false},
		{"without replacement too large", 5, false, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, errGot := orig.Sample(tc.n, tc.replace)
			want, errWant := Sample(orig, tc.n, tc.replace)
			if (errGot != nil) != (errWant != nil) {
				t.Fatalf("error mismatch: got %v, want %v", errGot, errWant)
			}
			if errGot != nil {
				if !tc.expectErr {
					t.Errorf("unexpected error: %v", errGot)
				}
				return
			}
			if len(got) != tc.n {
				t.Errorf("result length %d, want %d", len(got), tc.n)
			}
			if !tc.replace {
				if !dataAllInSet(got, orig) {
					t.Errorf("sample contains values not in original slice")
				}
				if !dataAllInSet(want, orig) {
					t.Errorf("expected sample contains values not in original slice")
				}
			}
		})
	}
}

func TestFloat64Data_SampleVariance(t *testing.T) {
	cases := []struct {
		name string
		data Float64Data
	}{
		{"normal", Float64Data{1, 2, 3, 4, 5}},
		{"empty", Float64Data{}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, errGot := tc.data.SampleVariance()
			want, errWant := SampleVariance(tc.data)
			if (errGot != nil) != (errWant != nil) {
				t.Fatalf("error mismatch: got %v, want %v", errGot, errWant)
			}
			if errGot != nil {
				return
			}
			if math.Abs(got-want) > 1e-9 {
				t.Errorf("SampleVariance mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_Sigmoid(t *testing.T) {
	cases := []struct {
		name string
		data Float64Data
	}{
		{"normal", Float64Data{-2, 0, 2}},
		{"empty", Float64Data{}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, errGot := tc.data.Sigmoid()
			want, errWant := Sigmoid(tc.data)
			if (errGot != nil) != (errWant != nil) {
				t.Fatalf("error mismatch: got %v, want %v", errGot, errWant)
			}
			if errGot != nil {
				return
			}
			if !dataSlicesClose(got, want) {
				t.Errorf("Sigmoid result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_SoftMax(t *testing.T) {
	cases := []struct {
		name string
		data Float64Data
	}{
		{"normal", Float64Data{1, 2, 3}},
		{"empty", Float64Data{}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, errGot := tc.data.SoftMax()
			want, errWant := SoftMax(tc.data)
			if (errGot != nil) != (errWant != nil) {
				t.Fatalf("error mismatch: got %v, want %v", errGot, errWant)
			}
			if errGot != nil {
				return
			}
			if !dataSlicesClose(got, want) {
				t.Errorf("SoftMax result mismatch: got %v, want %v", got, want)
			}
			sum := 0.0
			for _, v := range got {
				sum += v
			}
			if math.Abs(sum-1) > 1e-9 {
				t.Errorf("SoftMax probabilities sum %v, want 1", sum)
			}
		})
	}
}

func TestFloat64Data_Spearman(t *testing.T) {
	cases := []struct {
		name    string
		a, b    Float64Data
		want    float64
		wantErr bool
	}{
		{"identical", Float64Data{1, 2, 3, 4, 5}, Float64Data{1, 2, 3, 4, 5}, 1, false},
		{"reversed", Float64Data{1, 2, 3, 4, 5}, Float64Data{5, 4, 3, 2, 1}, -1, false},
		{"mismatched", Float64Data{1, 2, 3}, Float64Data{1, 2}, 0, true},
		{"empty", Float64Data{}, Float64Data{}, 0, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.a.Spearman(tc.b)
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
				t.Errorf("Spearman = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_StandardDeviationPopulation(t *testing.T) {
	data := Float64Data{1, 2, 3, 4, 5}
	got, err := data.StandardDeviationPopulation()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := math.Sqrt(2)
	if math.Abs(got-want) > 1e-9 {
		t.Errorf("StandardDeviationPopulation = %v, want %v", got, want)
	}
	empty := Float64Data{}
	if _, err := empty.StandardDeviationPopulation(); err == nil {
		t.Errorf("expected error for empty input")
	}
}

func TestFloat64Data_StandardDeviationSample(t *testing.T) {
	data := Float64Data{1, 2, 3, 4, 5}
	got, err := data.StandardDeviationSample()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := math.Sqrt(2.5)
	if math.Abs(got-want) > 1e-9 {
		t.Errorf("StandardDeviationSample = %v, want %v", got, want)
	}
	empty := Float64Data{}
	if _, err := empty.StandardDeviationSample(); err == nil {
		t.Errorf("expected error for empty input")
	}
}

func TestFloat64Data_Swap(t *testing.T) {
	data := Float64Data{10, 20, 30, 40}
	data.Swap(1, 3)
	expected := Float64Data{10, 40, 30, 20}
	if !dataSlicesClose(data, expected) {
		t.Errorf("Swap result %v, want %v", data, expected)
	}
}

func TestFloat64Data_StandardDeviation(t *testing.T) {
	cases := []struct {
		name string
		data Float64Data
	}{
		{"normal", Float64Data{1, 2, 3, 4, 5}},
		{"empty", Float64Data{}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.StandardDeviation()
			want, wantErr := StandardDeviation(tc.data)
			if (err != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", err, wantErr)
			}
			if err == nil && !dataFloatClose(got, want) {
				t.Errorf("result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_Variance(t *testing.T) {
	cases := []struct {
		name string
		data Float64Data
	}{
		{"normal", Float64Data{1, 2, 3, 4, 5}},
		{"empty", Float64Data{}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.data.Variance()
			want, wantErr := Variance(tc.data)
			if (err != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", err, wantErr)
			}
			if err == nil && !dataFloatClose(got, want) {
				t.Errorf("result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestFloat64Data_Trimean(t *testing.T) {
	cases := []struct {
		name string
		recv Float64Data
		arg  Float64Data
	}{
		{"normal", Float64Data{1, 2, 3, 4, 5}, Float64Data{1, 2, 3, 4, 5}},
		{"empty", Float64Data{}, Float64Data{}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := tc.recv.Trimean(tc.arg)
			want, wantErr := Trimean(tc.arg)
			if (err != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", err, wantErr)
			}
			if err == nil && !dataFloatClose(got, want) {
				t.Errorf("result mismatch: got %v, want %v", got, want)
			}
		})
	}
}
