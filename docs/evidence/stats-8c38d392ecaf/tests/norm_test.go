package stats

import (
	"math"
	"testing"
)

// Helper to compare float64 with tolerance
func normApproxEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	if math.IsInf(a, 0) && math.IsInf(b, 0) {
		return math.Signbit(a) == math.Signbit(b)
	}
	return math.Abs(a-b) <= eps
}

func TestNormPpf(t *testing.T) {
	cases := []struct {
		name          string
		p, loc, scale float64
		want          float64
		wantNaN       bool
		wantInf       int // -1 for -Inf, 1 for +Inf, 0 otherwise
	}{
		{"pOutOfRangeLow", -0.1, 0, 1, 0, true, 0},
		{"pOutOfRangeHigh", 1.2, 0, 1, 0, true, 0},
		{"pZero", 0, 0, 1, 0, false, -1},
		{"pOne", 1, 0, 1, 0, false, 1},
		{"pMedian", 0.5, 2.0, 3.0, 2.0, false, 0},
		{"pLowTail", 0.01, 0, 1, 0, false, 0},
		{"pHighTail", 0.99, 0, 1, 0, false, 0},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormPpf(tc.p, tc.loc, tc.scale)
			if tc.wantNaN {
				if !math.IsNaN(got) {
					t.Errorf("expected NaN, got %v", got)
				}
				return
			}
			if tc.wantInf != 0 {
				if !math.IsInf(got, tc.wantInf) {
					t.Errorf("expected Inf(%d), got %v", tc.wantInf, got)
				}
				return
			}
			if tc.name == "pMedian" {
				if !normApproxEqual(got, tc.want) {
					t.Errorf("median expected %v, got %v", tc.want, got)
				}
				return
			}
			// For low/high tail just check direction relative to loc and finiteness
			if math.IsNaN(got) || math.IsInf(got, 0) {
				t.Errorf("unexpected NaN/Inf for %s", tc.name)
			}
			if tc.name == "pLowTail" && !(got < tc.loc) {
				t.Errorf("low tail expected value < loc, got %v", got)
			}
			if tc.name == "pHighTail" && !(got > tc.loc) {
				t.Errorf("high tail expected value > loc, got %v", got)
			}
		})
	}
}

func TestNormMoment(t *testing.T) {
	loc, scale := 2.0, 3.0
	cases := []struct {
		name string
		n    int
		want float64
	}{
		{"negative", -1, 0},
		{"zero", 0, 1},
		{"one", 1, loc},
		{"two", 2, loc*loc + scale*scale},
		{"three", 3, loc*loc*loc + 3*loc*scale*scale},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormMoment(tc.n, loc, scale)
			if !normApproxEqual(got, tc.want) {
				t.Errorf("n=%d expected %v, got %v", tc.n, tc.want, got)
			}
		})
	}
	// Additional case where both loc and scale are zero
	if got := NormMoment(5, 0, 0); got != 0 {
		t.Errorf("all zero parameters expected 0, got %v", got)
	}
}

func TestNcr(t *testing.T) {
	cases := []struct {
		name     string
		n, r     int
		want     int
		overflow bool
	}{
		{"rNegative", 5, -1, 0, false},
		{"rGreaterThanN", 3, 5, 0, false},
		{"chooseZero", 5, 0, 1, false},
		{"chooseN", 5, 5, 1, false},
		{"chooseOne", 7, 1, 7, false},
		{"symmetry", 5, 4, 5, false},
		{"overflow", math.MaxInt, 2, math.MaxInt, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := Ncr(tc.n, tc.r)
			if tc.overflow {
				if got != math.MaxInt {
					t.Errorf("expected overflow MaxInt, got %v", got)
				}
				return
			}
			if got != tc.want {
				t.Errorf("Ncr(%d,%d) expected %d, got %d", tc.n, tc.r, tc.want, got)
			}
		})
	}
}

func TestNormBoxMullerRvs(t *testing.T) {
	cases := []struct {
		name string
		size int
	}{
		{"zero", 0},
		{"one", 1},
		{"two", 2},
		{"odd", 5},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			vals := NormBoxMullerRvs(0, 1, tc.size)
			if len(vals) != tc.size {
				t.Fatalf("expected %d values, got %d", tc.size, len(vals))
			}
			for i, v := range vals {
				if math.IsNaN(v) || math.IsInf(v, 0) {
					t.Fatalf("value %d is not finite: %v", i, v)
				}
			}
		})
	}
}

func TestNormStats(t *testing.T) {
	loc, scale := 2.5, 1.5
	cases := []struct {
		name    string
		moments string
		want    []float64
	}{
		{"mean", "m", []float64{loc}},
		{"variance", "v", []float64{scale * scale}},
		{"skew", "s", []float64{0.0}},
		{"kurtosis", "k", []float64{0.0}},
		{"meanVar", "mv", []float64{loc, scale * scale}},
		{"mixed", "svk", []float64{scale * scale, 0.0, 0.0}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormStats(loc, scale, tc.moments)
			if len(got) != len(tc.want) {
				t.Fatalf("expected %d elements, got %d", len(tc.want), len(got))
			}
			for i := range got {
				if !normApproxEqual(got[i], tc.want[i]) {
					t.Fatalf("index %d expected %v, got %v", i, tc.want[i], got[i])
				}
			}
		})
	}
}

func TestNormFit(t *testing.T) {
	cases := []struct {
		name     string
		data     []float64
		wantMean float64
		wantStd  float64
	}{
		{
			name:     "simple",
			data:     []float64{1, 2, 3, 4},
			wantMean: 2.5,
			wantStd:  math.Sqrt(1.25), // ≈1.11803398875
		},
		{
			name:     "empty",
			data:     []float64{},
			wantMean: math.NaN(),
			wantStd:  math.NaN(),
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormFit(tc.data)
			if math.IsNaN(tc.wantMean) {
				if !math.IsNaN(got[0]) {
					t.Errorf("expected mean NaN, got %v", got[0])
				}
			} else if math.Abs(got[0]-tc.wantMean) > 1e-12 {
				t.Errorf("mean mismatch: got %v want %v", got[0], tc.wantMean)
			}
			if math.IsNaN(tc.wantStd) {
				if !math.IsNaN(got[1]) {
					t.Errorf("expected std NaN, got %v", got[1])
				}
			} else if math.Abs(got[1]-tc.wantStd) > 1e-12 {
				t.Errorf("std mismatch: got %v want %v", got[1], tc.wantStd)
			}
		})
	}
}

func TestNormPpfRvs(t *testing.T) {
	size := 5
	loc, scale := 0.0, 1.0
	vals := NormPpfRvs(loc, scale, size)
	if len(vals) != size {
		t.Fatalf("expected %d values, got %d", size, len(vals))
	}
	for i, v := range vals {
		if math.IsNaN(v) || math.IsInf(v, 0) {
			t.Errorf("value at index %d is not finite: %v", i, v)
		}
	}
}

func TestNormLogCdf(t *testing.T) {
	cases := []struct {
		name          string
		x, loc, scale float64
		want          float64
	}{
		{
			name: "zPositive",
			x:    1, loc: 0, scale: 1,
			want: math.Log1p(-0.5 * math.Erfc(1/math.Sqrt2)),
		},
		{
			name: "zNonPositive",
			x:    -1, loc: 0, scale: 1,
			want: normLogTail(1), // -z = 1
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormLogCdf(tc.x, tc.loc, tc.scale)
			if math.Abs(got-tc.want) > 1e-12 {
				t.Errorf("NormLogCdf(%v) = %v, want %v", tc.x, got, tc.want)
			}
		})
	}
}

func TestNormLogSf(t *testing.T) {
	cases := []struct {
		name          string
		x, loc, scale float64
		want          float64
	}{
		{
			name: "zNegative",
			x:    -1, loc: 0, scale: 1,
			want: math.Log1p(-0.5 * math.Erfc(1/math.Sqrt2)), // -z = 1
		},
		{
			name: "zNonNegative",
			x:    1, loc: 0, scale: 1,
			want: normLogTail(1),
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormLogSf(tc.x, tc.loc, tc.scale)
			if math.Abs(got-tc.want) > 1e-12 {
				t.Errorf("NormLogSf(%v) = %v, want %v", tc.x, got, tc.want)
			}
		})
	}
}
