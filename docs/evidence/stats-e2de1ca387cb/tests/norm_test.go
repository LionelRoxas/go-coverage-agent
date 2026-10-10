package stats

import (
	"math"
	"testing"
)

func approxEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	if math.IsInf(a, 0) && math.IsInf(b, 0) && (a > 0) == (b > 0) {
		return true
	}
	return math.Abs(a-b) <= eps
}

func TestNormPpf(t *testing.T) {
	cases := []struct {
		name    string
		p       float64
		loc     float64
		scale   float64
		want    float64
		wantNaN bool
		wantInf bool
	}{
		{"p<0", -0.1, 0, 1, math.NaN(), true, false},
		{"p>1", 1.2, 0, 1, math.NaN(), true, false},
		{"p==0", 0, 0, 1, math.Inf(-1), false, true},
		{"p==1", 1, 0, 1, math.Inf(1), false, true},
		{"median", 0.5, 2.0, 3.0, 2.0, false, false},
		{"low tail", 0.01, 0, 1, -2.3263478740408408, false, false},
		{"high tail", 0.99, 0, 1, 2.3263478740408408, false, false},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormPpf(tc.p, tc.loc, tc.scale)
			if tc.wantNaN {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN, got %v", got)
				}
				return
			}
			if tc.wantInf {
				if !math.IsInf(got, 0) {
					t.Fatalf("expected Inf, got %v", got)
				}
				// sign check
				if (tc.want > 0) != (got > 0) {
					t.Fatalf("expected Inf sign %v, got %v", tc.want, got)
				}
				return
			}
			if !approxEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}

func TestNormMoment(t *testing.T) {
	cases := []struct {
		name  string
		n     int
		loc   float64
		scale float64
		want  float64
	}{
		{"n<0", -1, 0, 1, 0},
		{"n==0", 0, 5, 2, 1},
		{"n==1", 1, 5, 2, 5},
		{"n==2 nonzero", 2, 2, 3, 13},   // 2^2 + 3^2
		{"n==2 zero loc", 2, 0, 4, 16},  // variance only
		{"n==2 zero var", 2, 7, 0, 49},  // loc^2
		{"n==3", 3, 2, 3, 2*13 + 2*9*2}, // loc*M2 + 2*var*M1
		{"n==3 zero var", 3, 5, 0, 125}, // 5^3
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormMoment(tc.n, tc.loc, tc.scale)
			if !approxEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}

func TestNcr(t *testing.T) {
	cases := []struct {
		name     string
		n, r     int
		want     int
		overflow bool
	}{
		{"r<0", 5, -1, 0, false},
		{"r>n", 3, 5, 0, false},
		{"symmetry", 5, 4, 5, false}, // same as C(5,1)
		{"normal", 10, 3, 120, false},
		{"overflow", 67, 33, math.MaxInt, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := Ncr(tc.n, tc.r)
			if tc.overflow {
				if got != math.MaxInt {
					t.Fatalf("expected MaxInt overflow, got %d", got)
				}
				return
			}
			if got != tc.want {
				t.Fatalf("expected %d, got %d", tc.want, got)
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
		{"even", 4},
		{"odd", 5},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			vals := NormBoxMullerRvs(0, 1, tc.size)
			if len(vals) != tc.size {
				t.Fatalf("expected length %d, got %d", tc.size, len(vals))
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
		{"all", "mvsk", []float64{loc, scale * scale, 0.0, 0.0}},
		{"none", "", []float64{}},
		{"unknown", "x", []float64{}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormStats(loc, scale, tc.moments)
			if len(got) != len(tc.want) {
				t.Fatalf("expected length %d, got %d", len(tc.want), len(got))
			}
			for i := range got {
				if !approxEqual(got[i], tc.want[i]) {
					t.Fatalf("at index %d expected %v, got %v", i, tc.want[i], got[i])
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
		{"simple", []float64{1, 2, 3, 4, 5}, 3, math.Sqrt(2)},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormFit(tc.data)
			if math.Abs(got[0]-tc.wantMean) > 1e-9 {
				t.Fatalf("mean got %v want %v", got[0], tc.wantMean)
			}
			if math.Abs(got[1]-tc.wantStd) > 1e-9 {
				t.Fatalf("std got %v want %v", got[1], tc.wantStd)
			}
		})
	}
}

func TestNormPpfRvs(t *testing.T) {
	size := 7
	vals := NormPpfRvs(0, 1, size)
	if len(vals) != size {
		t.Fatalf("expected length %d got %d", size, len(vals))
	}
	for i, v := range vals {
		if math.IsNaN(v) || math.IsInf(v, 0) {
			t.Fatalf("value %d is not finite: %v", i, v)
		}
	}
}

func TestNormLogCdf(t *testing.T) {
	cases := []struct {
		name          string
		x, loc, scale float64
	}{
		{"positive_z", 2, 0, 1},
		{"negative_z", -2, 0, 1},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormLogCdf(tc.x, tc.loc, tc.scale)
			z := (tc.x - tc.loc) / tc.scale
			want := math.Log(0.5 * math.Erfc(-z/math.Sqrt2))
			if math.Abs(got-want) > 1e-12 {
				t.Fatalf("logcdf got %v want %v (z=%v)", got, want, z)
			}
		})
	}
}

func TestNormLogSf(t *testing.T) {
	cases := []struct {
		name          string
		x, loc, scale float64
	}{
		{"positive_z", 2, 0, 1},
		{"negative_z", -2, 0, 1},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormLogSf(tc.x, tc.loc, tc.scale)
			z := (tc.x - tc.loc) / tc.scale
			want := math.Log(0.5 * math.Erfc(z/math.Sqrt2))
			if math.Abs(got-want) > 1e-12 {
				t.Fatalf("logsf got %v want %v (z=%v)", got, want, z)
			}
		})
	}
}

func TestNormLogTail(t *testing.T) {
	t.Run("q_ge_smallest", func(t *testing.T) {
		z := 0.0
		got := normLogTail(z)
		q := 0.5 * math.Erfc(z/math.Sqrt2)
		want := math.Log(q)
		if math.Abs(got-want) > 1e-12 {
			t.Fatalf("normLogTail(%v)=%v want %v", z, got, want)
		}
	})
	t.Run("large_z_approx", func(t *testing.T) {
		z := 40.0
		got := normLogTail(z)
		if math.IsNaN(got) || math.IsInf(got, 0) {
			t.Fatalf("normLogTail(%v) returned non-finite %v", z, got)
		}
		leading := -0.5*z*z - math.Log(z) - 0.5*math.Log(2*math.Pi)
		if got > leading {
			t.Fatalf("normLogTail(%v)=%v not less than leading term %v", z, got, leading)
		}
		if got < leading-20 {
			t.Fatalf("normLogTail(%v)=%v too far below leading term %v", z, got, leading)
		}
	})
}
