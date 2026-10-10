package stats

import (
	"math"
	"math/rand"
	"testing"
)

func approxEqual(a, b float64) bool {
	const eps = 1e-6
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
		name          string
		p, loc, scale float64
		want          float64
		wantNaN       bool
		wantInf       int // -1 for -Inf, 1 for +Inf, 0 otherwise
	}{
		{"p<0", -0.1, 0, 1, 0, true, 0},
		{"p>1", 1.2, 0, 1, 0, true, 0},
		{"p==0", 0, 0, 1, 0, false, -1},
		{"p==1", 1, 0, 1, 0, false, 1},
		{"p<plow", 0.001, 0, 1, -3.09023230616781, false, 0},
		{"p>phigh", 0.999, 0, 1, 3.09023230616781, false, 0},
		{"p=0.5", 0.5, 2, 3, 2, false, 0},
		{"p=0.1", 0.1, 0, 1, -1.2815515655446004, false, 0},
		{"p=0.9", 0.9, 0, 1, 1.2815515655446004, false, 0},
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
			if tc.wantInf != 0 {
				if !math.IsInf(got, tc.wantInf) {
					t.Fatalf("expected Inf(%d), got %v", tc.wantInf, got)
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
		name       string
		n          int
		loc, scale float64
		want       float64
	}{
		{"n<0", -1, 0, 1, 0},
		{"n=0", 0, 0, 1, 1},
		{"n=1", 1, 2.5, 1, 2.5},
		{"loc non-zero, scale zero", 3, 2, 0, 8},
		{"loc zero, variance non-zero", 2, 0, 2, 4},
		{"both non-zero", 2, 1, 2, 5},
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
		name    string
		n, r    int
		want    int
		wantMax bool
	}{
		{"r<0", 5, -1, 0, false},
		{"r>n", 3, 5, 0, false},
		{"swap", 5, 4, 5, false},
		{"normal", 5, 2, 10, false},
		{"overflow", 100, 50, math.MaxInt, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := Ncr(tc.n, tc.r)
			if tc.wantMax {
				if got != math.MaxInt {
					t.Fatalf("expected MaxInt, got %d", got)
				}
			} else if got != tc.want {
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
		{"odd", 5},
		{"even", 4},
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
					t.Fatalf("value at %d is not finite: %v", i, v)
				}
			}
		})
	}
}

func TestNormStats(t *testing.T) {
	loc, scale := 3.0, 2.0
	cases := []struct {
		name    string
		moments string
		want    []float64
	}{
		{"all", "mvsk", []float64{loc, scale * scale, 0, 0}},
		{"mean only", "m", []float64{loc}},
		{"variance only", "v", []float64{scale * scale}},
		{"empty", "", []float64{}},
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
					t.Fatalf("at %d expected %v got %v", i, tc.want[i], got[i])
				}
			}
		})
	}
}

func normFloatClose(a, b float64) bool {
	const eps = 1e-12
	return math.Abs(a-b) <= eps
}

func TestNormFit(t *testing.T) {
	cases := []struct {
		name     string
		data     []float64
		wantMean float64
		wantStd  float64
	}{
		{"simple", []float64{1, 2, 3, 4, 5}, 3, math.Sqrt(2)},
		{"single", []float64{42}, 42, 0},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormFit(tc.data)
			if !normFloatClose(got[0], tc.wantMean) {
				t.Fatalf("mean got %v want %v", got[0], tc.wantMean)
			}
			if !normFloatClose(got[1], tc.wantStd) {
				t.Fatalf("std got %v want %v", got[1], tc.wantStd)
			}
		})
	}
}

func TestNormPpfRvs(t *testing.T) {
	size := 5
	vals := NormPpfRvs(0, 1, size)
	if len(vals) != size {
		t.Fatalf("expected length %d got %d", size, len(vals))
	}
	for i, v := range vals {
		if math.IsNaN(v) || math.IsInf(v, 0) {
			t.Fatalf("value %d is not finite: %v", i, v)
		}
	}
	zero := NormPpfRvs(0, 1, 0)
	if len(zero) != 0 {
		t.Fatalf("expected empty slice for size 0, got length %d", len(zero))
	}
}

func TestNormLogCdf(t *testing.T) {
	cases := []struct {
		name          string
		x, loc, scale float64
	}{
		{"positive_z", 1, 0, 1},
		{"negative_z", -1, 0, 1},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormLogCdf(tc.x, tc.loc, tc.scale)
			z := (tc.x - tc.loc) / tc.scale
			var want float64
			if z > 0 {
				want = math.Log1p(-0.5 * math.Erfc(z/math.Sqrt2))
			} else {
				want = normLogTail(-z)
			}
			if !normFloatClose(got, want) {
				t.Fatalf("got %v want %v", got, want)
			}
		})
	}
}

func TestNormLogSf(t *testing.T) {
	cases := []struct {
		name          string
		x, loc, scale float64
	}{
		{"negative_z", -1, 0, 1},
		{"nonnegative_z", 1, 0, 1},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormLogSf(tc.x, tc.loc, tc.scale)
			z := (tc.x - tc.loc) / tc.scale
			var want float64
			if z < 0 {
				want = math.Log1p(-0.5 * math.Erfc(-z/math.Sqrt2))
			} else {
				want = normLogTail(z)
			}
			if !normFloatClose(got, want) {
				t.Fatalf("got %v want %v", got, want)
			}
		})
	}
}

func TestNormLogTail(t *testing.T) {
	cases := []struct {
		name string
		z    float64
	}{
		{"large_q", 0.5},
		{"small_q", 10},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := normLogTail(tc.z)
			q := 0.5 * math.Erfc(tc.z/math.Sqrt2)
			if q >= normSmallestNormal {
				want := math.Log(q)
				if !normFloatClose(got, want) {
					t.Fatalf("large_q branch: got %v want %v", got, want)
				}
			} else {
				r := 1 / (tc.z * tc.z)
				want := -0.5*tc.z*tc.z - math.Log(tc.z) - 0.5*math.Log(2*math.Pi) + math.Log1p(r*(-1+r*(3+r*(-15+r*105))))
				if !normFloatClose(got, want) {
					t.Fatalf("small_q branch: got %v want %v", got, want)
				}
			}
		})
	}
}

func TestNormInterval_Uncovered(t *testing.T) {
	cases := []struct {
		name              string
		alpha, loc, scale float64
		wantLow, wantHigh float64
		wantInf           bool
	}{
		{"Standard95", 0.95, 0, 1, -1.959963984540054, 1.959963984540054, false},
		{"AllInf", 1.0, 2, 3, math.Inf(-1), math.Inf(1), true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormInterval(tc.alpha, tc.loc, tc.scale)
			if tc.wantInf {
				if !math.IsInf(got[0], -1) || !math.IsInf(got[1], 1) {
					t.Fatalf("expected infinities, got %v", got)
				}
				return
			}
			if !normFloatClose(got[0], tc.wantLow) || !normFloatClose(got[1], tc.wantHigh) {
				t.Fatalf("interval %v, want [%v,%v]", got, tc.wantLow, tc.wantHigh)
			}
		})
	}
}

func TestNormLogPdf_Uncovered(t *testing.T) {
	cases := []struct {
		name          string
		x, loc, scale float64
		want          float64
	}{
		{"StandardZero", 0, 0, 1, -0.5 * math.Log(2*math.Pi)},
		{"Scaled", 2, 1, 2, func() float64 {
			z := (2.0 - 1.0) / 2.0
			return -0.5*z*z - math.Log(2.0) - 0.5*math.Log(2*math.Pi)
		}()},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormLogPdf(tc.x, tc.loc, tc.scale)
			if math.Abs(got-tc.want) > 1e-12 {
				t.Fatalf("got %v want %v", got, tc.want)
			}
		})
	}
}

func TestNormLogTail_Uncovered(t *testing.T) {
	cases := []struct {
		name string
		z    float64
	}{
		{"Moderate", 0},
		{"Large", 10},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := normLogTail(tc.z)
			ref := math.Log(0.5 * math.Erfc(tc.z/math.Sqrt2))
			if math.Abs(got-ref) > 1e-12 {
				t.Fatalf("z=%v got %v ref %v diff %v", tc.z, got, ref, math.Abs(got-ref))
			}
		})
	}
}

func TestNormCdf_Uncovered(t *testing.T) {
	cases := []struct {
		name          string
		x, loc, scale float64
		want          float64
	}{
		{"ZeroMean", 0, 0, 1, 0.5},
		{"OneStd", 1, 0, 1, 0.8413447460685429},
		{"MinusOneStd", -1, 0, 1, 0.15865525393145707},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormCdf(tc.x, tc.loc, tc.scale)
			if math.Abs(got-tc.want) > 1e-12 {
				t.Fatalf("got %v want %v", got, tc.want)
			}
		})
	}
}

func TestNormEntropy_Uncovered(t *testing.T) {
	cases := []struct {
		name       string
		loc, scale float64
		want       float64
	}{
		{"ScaleOne", 0, 1, math.Log(math.Sqrt(2 * math.Pi * math.E))},
		{"ScaleTwoPointFive", 0, 2.5, math.Log(2.5 * math.Sqrt(2*math.Pi*math.E))},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormEntropy(tc.loc, tc.scale)
			if math.Abs(got-tc.want) > 1e-12 {
				t.Fatalf("got %v want %v", got, tc.want)
			}
		})
	}
}

func TestNormIsf(t *testing.T) {
	cases := []struct {
		name       string
		p, loc, sc float64
		want       float64
	}{
		{name: "p0.5", p: 0.5, loc: 2.0, sc: 3.0, want: 2.0}, // NormPpf(0.5)=0
		{name: "p0.1", p: 0.1, loc: -1.0, sc: 2.0, want: -1.0 - 2.0*NormPpf(0.1, 0, 1)},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormIsf(tc.p, tc.loc, tc.sc)
			if math.Abs(got-tc.want) > 1e-12 {
				t.Fatalf("NormIsf(%v,%v,%v) = %v, want %v", tc.p, tc.loc, tc.sc, got, tc.want)
			}
		})
	}
}

func TestNormMean(t *testing.T) {
	cases := []struct {
		name       string
		loc, scale float64
		want       float64
	}{
		{name: "zero", loc: 0, scale: 1, want: 0},
		{name: "positive", loc: 5.3, scale: 2.1, want: 5.3},
		{name: "negative", loc: -2.7, scale: 0.5, want: -2.7},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormMean(tc.loc, tc.scale)
			if got != tc.want {
				t.Fatalf("NormMean(%v,%v) = %v, want %v", tc.loc, tc.scale, got, tc.want)
			}
		})
	}
}

func TestNormMedian(t *testing.T) {
	cases := []struct {
		name       string
		loc, scale float64
		want       float64
	}{
		{name: "zero", loc: 0, scale: 1, want: 0},
		{name: "positive", loc: 4.2, scale: 3.3, want: 4.2},
		{name: "negative", loc: -1.5, scale: 0.8, want: -1.5},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormMedian(tc.loc, tc.scale)
			if got != tc.want {
				t.Fatalf("NormMedian(%v,%v) = %v, want %v", tc.loc, tc.scale, got, tc.want)
			}
		})
	}
}

func TestNormPdf(t *testing.T) {
	cases := []struct {
		name       string
		x, loc, sc float64
		want       float64
	}{
		// Standard normal at 0: 1/sqrt(2π)
		{name: "stdZero", x: 0, loc: 0, sc: 1, want: 1 / math.Sqrt(2*math.Pi)},
		// Non‑standard with (x‑loc)=0, scale=2 => 1/(2*sqrt(2π))
		{name: "nonStdZero", x: 5, loc: 5, sc: 2, want: 1 / (2 * math.Sqrt(2*math.Pi))},
		// General case
		{name: "general", x: 3, loc: 1, sc: 2, want: (math.Exp(-math.Pow(3-1, 2) / (2 * math.Pow(2, 2)))) / (2 * math.Sqrt(2*math.Pi))},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormPdf(tc.x, tc.loc, tc.sc)
			if math.Abs(got-tc.want) > 1e-12 {
				t.Fatalf("NormPdf(%v,%v,%v) = %v, want %v", tc.x, tc.loc, tc.sc, got, tc.want)
			}
		})
	}
}

func TestNormLogTail_Branches(t *testing.T) {
	cases := []struct {
		name        string
		z           float64
		expectExact bool
	}{
		{"small z", 0.5, true},
		{"large z", 10.0, false},
	}
	var smallResult float64
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := normLogTail(tc.z)
			if tc.expectExact {
				expected := math.Log(0.5 * math.Erfc(tc.z/math.Sqrt2))
				if diff := math.Abs(got - expected); diff > 1e-12 {
					t.Fatalf("z=%v got %v expected %v diff %v", tc.z, got, expected, diff)
				}
				smallResult = got
			} else {
				if math.IsInf(got, 0) || math.IsNaN(got) {
					t.Fatalf("large z produced invalid result %v", got)
				}
				if smallResult == 0 {
					t.Fatalf("smallResult not set")
				}
				if got >= smallResult {
					t.Fatalf("large z result %v not less than small z result %v", got, smallResult)
				}
			}
		})
	}
}

func TestNormSample_Basic(t *testing.T) {
	rand.Seed(1)
	size := 1000
	loc := 2.0
	scale := 3.0
	samples := NormSample(loc, scale, size)
	if len(samples) != size {
		t.Fatalf("expected length %d got %d", size, len(samples))
	}
	for i, v := range samples {
		if math.IsNaN(v) || math.IsInf(v, 0) {
			t.Fatalf("sample %d is invalid %v", i, v)
		}
	}
	sum := 0.0
	for _, v := range samples {
		sum += v
	}
	mean := sum / float64(size)
	if math.Abs(mean-loc) > 0.2 {
		t.Fatalf("mean %v not close to loc %v", mean, loc)
	}
	// zero scale should produce constant values equal to loc
	samplesZero := NormSample(5.0, 0.0, 10)
	for _, v := range samplesZero {
		if v != 5.0 {
			t.Fatalf("expected constant value 5.0 got %v", v)
		}
	}
}

func TestNormStd_ReturnsScale(t *testing.T) {
	cases := []struct {
		loc, scale float64
	}{{0, 1}, {5, 2.5}, {-3, 0.0}}
	for _, c := range cases {
		got := NormStd(c.loc, c.scale)
		if got != c.scale {
			t.Fatalf("loc %v scale %v got %v", c.loc, c.scale, got)
		}
	}
}

func TestNormVar_ReturnsScaleSq(t *testing.T) {
	cases := []struct {
		loc, scale float64
	}{{0, 1}, {5, 2.5}, {-3, 0.0}}
	for _, c := range cases {
		got := NormVar(c.loc, c.scale)
		want := c.scale * c.scale
		if math.Abs(got-want) > 1e-12 {
			t.Fatalf("loc %v scale %v got %v want %v", c.loc, c.scale, got, want)
		}
	}
}

func normLogTailAlt(z float64) float64 {
	// Alternative implementation of the Mills ratio expansion used in normLogTail
	// for large z where the Erfc underflows.
	r := 1 / (z * z)
	return -0.5*z*z - math.Log(z) - 0.5*math.Log(2*math.Pi) +
		math.Log1p(r*(-1+r*(3+r*(-15+r*105))))
}

func TestNormLogTail_UncoveredLines(t *testing.T) {
	cases := []struct {
		name   string
		z      float64
		useAlt bool // true: compare with alternative implementation (large z branch)
	}{
		{name: "small_z", z: 0.0, useAlt: false},
		{name: "large_z", z: 40.0, useAlt: true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := normLogTail(tc.z)
			if tc.useAlt {
				// Expect the Mills‑ratio expansion path.
				exp := normLogTailAlt(tc.z)
				if math.IsNaN(got) || math.IsInf(got, 0) {
					t.Fatalf("normLogTail(%v) returned non‑finite %v", tc.z, got)
				}
				if math.Abs(got-exp) > 1e-12 {
					t.Fatalf("normLogTail(%v) = %v, want %v (alt)", tc.z, got, exp)
				}
			} else {
				// Expect the normal log‑survival path.
				q := 0.5 * math.Erfc(tc.z/math.Sqrt2)
				exp := math.Log(q)
				if math.Abs(got-exp) > 1e-12 {
					t.Fatalf("normLogTail(%v) = %v, want %v (log survival)", tc.z, got, exp)
				}
			}
		})
	}
}
