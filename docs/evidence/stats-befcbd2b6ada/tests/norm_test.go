package stats

import (
	"fmt"
	"math"
	"strconv"
	"testing"
)

func normApproxEqual(got, want float64, tol float64) bool {
	if math.IsNaN(want) {
		return math.IsNaN(got)
	}
	if math.IsInf(want, 1) {
		return math.IsInf(got, 1)
	}
	if math.IsInf(want, -1) {
		return math.IsInf(got, -1)
	}
	return math.Abs(got-want) <= tol
}

func TestNormPpf(t *testing.T) {
	cases := []struct {
		name          string
		p, loc, scale float64
		want          float64
		wantInf       int // 0=none, 1=+Inf, -1=-Inf, 2=NaN
	}{
		{"median", 0.5, 0, 1, 0, 0},
		{"lowerTail", 0.01, 0, 1, -2.3263478740408408, 0}, // known approx for 1%
		{"upperTail", 0.99, 0, 1, 2.3263478740408408, 0},
		{"scaled", 0.5, 2, 3, 2, 0},
		{"pZero", 0.0, 0, 1, 0, -1},
		{"pOne", 1.0, 0, 1, 0, 1},
		{"pNeg", -0.2, 0, 1, 0, 2},
		{"pOver", 1.2, 0, 1, 0, 2},
	}
	const tol = 1e-6
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormPpf(tc.p, tc.loc, tc.scale)
			switch tc.wantInf {
			case 2: // NaN
				if !math.IsNaN(got) {
					t.Errorf("expected NaN, got %v", got)
				}
			case 1:
				if !math.IsInf(got, 1) {
					t.Errorf("expected +Inf, got %v", got)
				}
			case -1:
				if !math.IsInf(got, -1) {
					t.Errorf("expected -Inf, got %v", got)
				}
			default:
				if !normApproxEqual(got, tc.want, tol) {
					t.Errorf("got %v, want %v (tol %v)", got, tc.want, tol)
				}
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
		{"negativeOrder", -1, 0, 1, 0},
		{"zeroOrder", 0, 0, 1, 1},
		{"firstOrder", 1, 5, 2, 5},
		{"secondOrderZeroLoc", 2, 0, 1, 1},    // variance = 1
		{"thirdOrderZeroScale", 3, 5, 0, 125}, // loc^3
	}
	const tol = 1e-9
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormMoment(tc.n, tc.loc, tc.scale)
			if math.IsNaN(tc.want) {
				if !math.IsNaN(got) {
					t.Errorf("expected NaN, got %v", got)
				}
				return
			}
			if math.Abs(got-tc.want) > tol {
				t.Errorf("got %v, want %v (tol %v)", got, tc.want, tol)
			}
		})
	}
}

func TestNcr(t *testing.T) {
	cases := []struct {
		name string
		n, r int
		want int
	}{
		{"invalidLow", 5, -1, 0},
		{"invalidHigh", 5, 6, 0},
		{"symmetry", 5, 4, 5}, // C(5,4)=5
		{"normal", 5, 2, 10},
		{"overflow", 100, 50, math.MaxInt},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := Ncr(tc.n, tc.r)
			if got != tc.want {
				t.Errorf("Ncr(%d,%d) = %d, want %d", tc.n, tc.r, got, tc.want)
			}
		})
	}
}

func TestNormBoxMullerRvs(t *testing.T) {
	sizes := []int{0, 4, 5}
	for _, size := range sizes {
		size := size
		t.Run("size"+strconv.Itoa(size), func(t *testing.T) {
			vals := NormBoxMullerRvs(0, 1, size)
			if len(vals) != size {
				t.Fatalf("expected length %d, got %d", size, len(vals))
			}
			for i, v := range vals {
				if math.IsNaN(v) || math.IsInf(v, 0) {
					t.Fatalf("value at index %d is not finite: %v", i, v)
				}
			}
		})
	}
}

func TestNormStats(t *testing.T) {
	loc := 3.0
	scale := 2.0
	cases := []struct {
		name    string
		moments string
		want    []float64
	}{
		{"meanOnly", "m", []float64{loc}},
		{"varOnly", "v", []float64{scale * scale}},
		{"skewOnly", "s", []float64{0.0}},
		{"kurtOnly", "k", []float64{0.0}},
		{"all", "mvsk", []float64{loc, scale * scale, 0.0, 0.0}},
		{"none", "", []float64{}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormStats(loc, scale, tc.moments)
			if len(got) != len(tc.want) {
				t.Fatalf("expected %d elements, got %d", len(tc.want), len(got))
			}
			const tol = 1e-12
			for i := range got {
				if math.Abs(got[i]-tc.want[i]) > tol {
					t.Fatalf("index %d: got %v, want %v", i, got[i], tc.want[i])
				}
			}
		})
	}
}

func TestNormFit(t *testing.T) {
	cases := []struct {
		name string
		data []float64
	}{
		{"simple", []float64{1, 2, 3, 4, 5}},
		{"single", []float64{42}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormFit(tc.data)
			n := float64(len(tc.data))
			sum := 0.0
			for _, v := range tc.data {
				sum += v
			}
			mean := sum / n
			var ss float64
			for _, v := range tc.data {
				d := v - mean
				ss += d * d
			}
			std := math.Sqrt(ss / n)
			if math.Abs(got[0]-mean) > 1e-12 || math.Abs(got[1]-std) > 1e-12 {
				t.Errorf("NormFit(%v) = %v, want [%v %v]", tc.data, got, mean, std)
			}
		})
	}
}

func TestNormPpfRvs(t *testing.T) {
	cases := []struct {
		name       string
		loc, scale float64
		size       int
	}{
		{"zero", 0, 1, 0},
		{"small", 0, 1, 5},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormPpfRvs(tc.loc, tc.scale, tc.size)
			if len(got) != tc.size {
				t.Fatalf("expected length %d, got %d", tc.size, len(got))
			}
			for i, v := range got {
				if math.IsNaN(v) || math.IsInf(v, 0) {
					t.Errorf("value %d is not finite: %v", i, v)
				}
			}
		})
	}
}

func TestNormLogCdf(t *testing.T) {
	cases := []struct {
		name          string
		x, loc, scale float64
	}{
		{"positive", 1, 0, 1},
		{"negative", -1, 0, 1},
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
			if math.Abs(got-want) > 1e-12 {
				t.Errorf("NormLogCdf mismatch, got %v want %v", got, want)
			}
		})
	}
}

func TestNormLogSf(t *testing.T) {
	cases := []struct {
		name          string
		x, loc, scale float64
	}{
		{"negative", -1, 0, 1},
		{"positive", 1, 0, 1},
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
			if math.Abs(got-want) > 1e-12 {
				t.Errorf("NormLogSf mismatch, got %v want %v", got, want)
			}
		})
	}
}

func TestNormLogTail(t *testing.T) {
	cases := []struct {
		name string
		z    float64
	}{
		{"normal", 0.0},
		{"large", 40.0},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := normLogTail(tc.z)
			q := 0.5 * math.Erfc(tc.z/math.Sqrt2)
			if q >= normSmallestNormal {
				want := math.Log(q)
				if math.Abs(got-want) > 1e-12 {
					t.Errorf("normLogTail normal branch got %v want %v", got, want)
				}
			} else {
				r := 1 / (tc.z * tc.z)
				want := -0.5*tc.z*tc.z - math.Log(tc.z) - 0.5*math.Log(2*math.Pi) +
					math.Log1p(r*(-1+r*(3+r*(-15+r*105))))
				if math.Abs(got-want) > 1e-10 {
					t.Errorf("normLogTail tail branch got %v want %v", got, want)
				}
			}
		})
	}
}

func TestNormInterval(t *testing.T) {
	cases := []struct {
		name              string
		alpha, loc, scale float64
	}{
		{"midAlpha", 0.5, 2.0, 3.0},
		{"zeroAlpha", 0.0, -1.5, 2.5},
	}
	const tol = 1e-12
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormInterval(tc.alpha, tc.loc, tc.scale)
			// expected using the same formula but computed explicitly
			z := NormPpf((1.0-tc.alpha)/2, 0, 1)
			expLow := tc.loc + tc.scale*z
			expHigh := tc.loc - tc.scale*z
			if !normApproxEqual(got[0], expLow, tol) {
				t.Errorf("low endpoint = %v, want %v", got[0], expLow)
			}
			if !normApproxEqual(got[1], expHigh, tol) {
				t.Errorf("high endpoint = %v, want %v", got[1], expHigh)
			}
			// interval should contain loc
			if !(got[0] <= tc.loc && tc.loc <= got[1]) && !(got[1] <= tc.loc && tc.loc <= got[0]) {
				t.Errorf("loc %v not inside interval %v", tc.loc, got)
			}
		})
	}
}

func TestNormLogPdf(t *testing.T) {
	const tol = 1e-12
	// standard normal at 0
	got := NormLogPdf(0, 0, 1)
	want := -0.5 * math.Log(2*math.Pi)
	if !normApproxEqual(got, want, tol) {
		t.Errorf("NormLogPdf(0,0,1) = %v, want %v", got, want)
	}
	// scaled normal
	x, loc, scale := 1.0, 0.0, 2.0
	got = NormLogPdf(x, loc, scale)
	z := (x - loc) / scale
	want = -0.5*z*z - math.Log(scale) - 0.5*math.Log(2*math.Pi)
	if !normApproxEqual(got, want, tol) {
		t.Errorf("NormLogPdf(%v,%v,%v) = %v, want %v", x, loc, scale, got, want)
	}
}

func TestNormCdf(t *testing.T) {
	const tol = 1e-12
	// standard normal at 0 should be 0.5
	got := NormCdf(0, 0, 1)
	if !normApproxEqual(got, 0.5, tol) {
		t.Errorf("NormCdf(0,0,1) = %v, want 0.5", got)
	}
	// standard normal at 1 ~ 0.8413447460685429
	got = NormCdf(1, 0, 1)
	want := 0.8413447460685429
	if !normApproxEqual(got, want, tol) {
		t.Errorf("NormCdf(1,0,1) = %v, want %v", got, want)
	}
}

func TestNormEntropy(t *testing.T) {
	const tol = 1e-12
	// scale = 1
	got := NormEntropy(0, 1)
	want := math.Log(math.Sqrt(2 * math.Pi * math.E))
	if !normApproxEqual(got, want, tol) {
		t.Errorf("NormEntropy(0,1) = %v, want %v", got, want)
	}
	// scale = 2
	got = NormEntropy(0, 2)
	want = math.Log(2 * math.Sqrt(2*math.Pi*math.E))
	if !normApproxEqual(got, want, tol) {
		t.Errorf("NormEntropy(0,2) = %v, want %v", got, want)
	}
}

func TestNormIsf(t *testing.T) {
	const tol = 1e-12
	probs := []float64{0.2, 0.5, 0.8}
	for _, p := range probs {
		p := p
		t.Run(fmt.Sprintf("p=%v", p), func(t *testing.T) {
			got := NormIsf(p, 0, 1)
			want := -NormPpf(p, 0, 1)
			if !normApproxEqual(got, want, tol) {
				t.Errorf("NormIsf(%v,0,1) = %v, want %v", p, got, want)
			}
		})
	}
}

func TestNormMean_Uncovered(t *testing.T) {
	cases := []struct {
		name  string
		loc   float64
		scale float64
	}{
		{"zero", 0, 1},
		{"positive", 5.5, 2.3},
		{"inf", math.Inf(1), 0},
		{"nan", math.NaN(), 3},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormMean(tc.loc, tc.scale)
			if math.IsNaN(tc.loc) {
				if !math.IsNaN(got) {
					t.Errorf("expected NaN, got %v", got)
				}
			} else if got != tc.loc {
				t.Errorf("expected %v, got %v", tc.loc, got)
			}
		})
	}
}

func TestNormMedian_Uncovered(t *testing.T) {
	cases := []struct {
		name  string
		loc   float64
		scale float64
	}{
		{"zero", 0, 1},
		{"positive", -2.1, 4.5},
		{"inf", math.Inf(-1), 0},
		{"nan", math.NaN(), 3},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormMedian(tc.loc, tc.scale)
			if math.IsNaN(tc.loc) {
				if !math.IsNaN(got) {
					t.Errorf("expected NaN, got %v", got)
				}
			} else if got != tc.loc {
				t.Errorf("expected %v, got %v", tc.loc, got)
			}
		})
	}
}

func TestNormPdf_Uncovered(t *testing.T) {
	cases := []struct {
		name          string
		x, loc, scale float64
		want          float64
	}{
		{"std_zero", 0, 0, 1, 1 / math.Sqrt(2*math.Pi)},
		{"std_one", 1, 0, 1, math.Exp(-0.5) / math.Sqrt(2*math.Pi)},
		{"nonunit", 2, 2, 3, 1 / (3 * math.Sqrt(2*math.Pi))},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormPdf(tc.x, tc.loc, tc.scale)
			if !normApproxEqual(got, tc.want, 1e-12) {
				t.Errorf("pdf mismatch: got %v want %v", got, tc.want)
			}
		})
	}
}

func TestNormStd_Uncovered(t *testing.T) {
	cases := []struct {
		name  string
		loc   float64
		scale float64
	}{
		{"zero", 0, 1},
		{"positive", -2.1, 4.5},
		{"inf", math.Inf(-1), 0},
		{"nan", math.NaN(), 3},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormStd(tc.loc, tc.scale)
			if math.IsNaN(tc.scale) {
				if !math.IsNaN(got) {
					t.Errorf("expected NaN, got %v", got)
				}
			} else if got != tc.scale {
				t.Errorf("expected %v, got %v", tc.scale, got)
			}
		})
	}
}

func TestNormVar_Uncovered(t *testing.T) {
	cases := []struct {
		loc   float64
		scale float64
		want  float64
	}{
		{0, 0, 0},
		{5, 1, 1},
		{-3, 2, 4},
		{10, -2.5, 6.25},
	}
	for _, tc := range cases {
		got := NormVar(tc.loc, tc.scale)
		if !normApproxEqual(got, tc.want, 1e-12) {
			t.Errorf("NormVar(%v,%v) = %v, want %v", tc.loc, tc.scale, got, tc.want)
		}
	}
}

func TestNormSample(t *testing.T) {
	cases := []struct {
		name   string
		loc    float64
		scale  float64
		size   int
		expect func(got []float64) bool
	}{
		{
			name:   "zero size",
			loc:    0,
			scale:  1,
			size:   0,
			expect: func(got []float64) bool { return len(got) == 0 },
		},
		{
			name:  "zero scale",
			loc:   5,
			scale: 0,
			size:  3,
			expect: func(got []float64) bool {
				if len(got) != 3 {
					return false
				}
				for _, v := range got {
					if v != 5 {
						return false
					}
				}
				return true
			},
		},
		{
			name:   "positive size",
			loc:    -2,
			scale:  1.5,
			size:   5,
			expect: func(got []float64) bool { return len(got) == 5 },
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := NormSample(tc.loc, tc.scale, tc.size)
			if !tc.expect(got) {
				t.Fatalf("unexpected result for case %s: got %v", tc.name, got)
			}
		})
	}
}
