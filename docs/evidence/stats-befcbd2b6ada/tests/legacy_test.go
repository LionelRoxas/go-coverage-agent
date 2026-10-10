package stats

import (
	"errors"
	"math"
	"testing"
)

func legacyFloatApproxEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	if math.IsInf(a, 0) && math.IsInf(b, 0) && (math.Signbit(a) == math.Signbit(b)) {
		return true
	}
	return math.Abs(a-b) <= eps
}

func legacyCoordsApproxEqual(a, b []Coordinate) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if !legacyFloatApproxEqual(a[i].X, b[i].X) || !legacyFloatApproxEqual(a[i].Y, b[i].Y) {
			return false
		}
	}
	return true
}

func TestExpReg(t *testing.T) {
	cases := []struct {
		name  string
		input []Coordinate
	}{
		{"empty", []Coordinate{}},
		{"single", []Coordinate{{X: 1, Y: 2}}},
		{"multiple", []Coordinate{{X: 0, Y: 1}, {X: 1, Y: 2}, {X: 2, Y: 4}}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, gotErr := ExpReg(tc.input)
			want, wantErr := ExponentialRegression(tc.input)
			if (gotErr != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", gotErr, wantErr)
			}
			if !legacyCoordsApproxEqual(got, want) {
				t.Fatalf("result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestLinReg(t *testing.T) {
	cases := []struct {
		name  string
		input []Coordinate
	}{
		{"empty", []Coordinate{}},
		{"single", []Coordinate{{X: 2, Y: 5}}},
		{"multiple", []Coordinate{{X: 0, Y: 0}, {X: 1, Y: 1}, {X: 2, Y: 2}}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, gotErr := LinReg(tc.input)
			want, wantErr := LinearRegression(tc.input)
			if (gotErr != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", gotErr, wantErr)
			}
			if !legacyCoordsApproxEqual(got, want) {
				t.Fatalf("result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestLogReg(t *testing.T) {
	cases := []struct {
		name  string
		input []Coordinate
	}{
		{"empty", []Coordinate{}},
		{"single", []Coordinate{{X: 1, Y: 10}}},
		{"multiple", []Coordinate{{X: 1, Y: 2}, {X: 2, Y: 4}, {X: 3, Y: 8}}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, gotErr := LogReg(tc.input)
			want, wantErr := LogarithmicRegression(tc.input)
			if (gotErr != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", gotErr, wantErr)
			}
			if !legacyCoordsApproxEqual(got, want) {
				t.Fatalf("result mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestStdDevP(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
	}{
		{"empty", Float64Data{}},
		{"single", Float64Data{5}},
		{"multiple", Float64Data{1, 2, 3, 4, 5}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, gotErr := StdDevP(tc.input)
			want, wantErr := StandardDeviationPopulation(tc.input)
			if (gotErr != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", gotErr, wantErr)
			}
			if !legacyFloatApproxEqual(got, want) {
				t.Fatalf("stddev mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestStdDevS(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
	}{
		{"empty", Float64Data{}},
		{"single", Float64Data{10}},
		{"multiple", Float64Data{2, 4, 4, 4, 5, 5, 7, 9}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, gotErr := StdDevS(tc.input)
			want, wantErr := StandardDeviationSample(tc.input)
			if (gotErr != nil) != (wantErr != nil) {
				t.Fatalf("error mismatch: got %v, want %v", gotErr, wantErr)
			}
			if !legacyFloatApproxEqual(got, want) {
				t.Fatalf("stddev mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestVarP(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{"Empty", Float64Data{}, 0, ErrEmptyInput},
		{"Single", Float64Data{5.0}, 0, nil},
		{"Two", Float64Data{2.0, 4.0}, 1.0, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := VarP(tc.input)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !legacyFloatApproxEqual(got, tc.want) {
				t.Errorf("VarP(%v) = %v, want %v", tc.input, got, tc.want)
			}
		})
	}
}

func TestVarS(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr bool
		wantNaN bool
	}{
		{"empty", Float64Data{}, 0, true, false},
		{"single", Float64Data{5}, 0, false, true},
		{"two", Float64Data{2, 4}, 2, false, false},
		{"three", Float64Data{1, 2, 3}, 1, false, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := VarS(tc.input)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.wantNaN {
				if !math.IsNaN(got) {
					t.Errorf("expected NaN, got %v", got)
				}
				return
			}
			if !legacyFloatApproxEqual(got, tc.want) {
				t.Errorf("VarS(%v) = %v, want %v", tc.input, got, tc.want)
			}
		})
	}
}
