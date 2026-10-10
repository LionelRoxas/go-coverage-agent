package stats

import (
	"errors"
	"math"
	"testing"
)

func ttestApproxEqual(got, want float64) bool {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= eps
}

func TestTTest(t *testing.T) {
	cases := []struct {
		name        string
		data1       Float64Data
		data2       Float64Data
		popMean     float64
		wantErr     error
		checkResult func(t *testing.T, tstat, pval float64)
	}{
		{
			name:    "empty data1",
			data1:   Float64Data{},
			wantErr: ErrEmptyInput,
		},
		{
			name:    "one‑sample n1<2",
			data1:   Float64Data{2.0},
			popMean: 0.0,
			wantErr: ErrBounds,
		},
		{
			name:    "one‑sample zero variance equal mean",
			data1:   Float64Data{5, 5, 5},
			popMean: 5.0,
			wantErr: nil,
			checkResult: func(t *testing.T, tstat, pval float64) {
				if tstat != 0 {
					t.Errorf("expected t=0, got %v", tstat)
				}
				if pval != 1 {
					t.Errorf("expected p=1, got %v", pval)
				}
			},
		},
		{
			name:    "one‑sample zero variance different mean",
			data1:   Float64Data{5, 5, 5},
			popMean: 3.0,
			wantErr: ErrBounds,
		},
		{
			name:    "two‑sample insufficient total",
			data1:   Float64Data{1},
			data2:   Float64Data{2},
			wantErr: ErrBounds,
		},
		{
			name:    "two‑sample normal case",
			data1:   Float64Data{1, 2, 3},
			data2:   Float64Data{4, 5, 6},
			wantErr: nil,
			checkResult: func(t *testing.T, tstat, pval float64) {
				if math.IsNaN(tstat) || math.IsNaN(pval) {
					t.Errorf("unexpected NaN result: t=%v p=%v", tstat, pval)
				}
				if pval < 0 || pval > 1 {
					t.Errorf("p‑value out of range [0,1]: %v", pval)
				}
			},
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			tstat, pval, err := TTest(tc.data1, tc.data2, tc.popMean)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil && tc.checkResult != nil {
				tc.checkResult(t, tstat, pval)
			}
		})
	}
}

func TestRegIncBeta(t *testing.T) {
	// x == 0
	if got := regIncBeta(2, 3, 0); got != 0 {
		t.Errorf("regIncBeta with x=0 expected 0, got %v", got)
	}
	// x == 1
	if got := regIncBeta(2, 3, 1); got != 1 {
		t.Errorf("regIncBeta with x=1 expected 1, got %v", got)
	}
	// typical values – result should be within [0,1]
	vals := []struct {
		a, b, x float64
	}{{2, 3, 0.5}, {0.5, 0.5, 0.3}, {5, 2, 0.7}}
	for _, v := range vals {
		got := regIncBeta(v.a, v.b, v.x)
		if math.IsNaN(got) {
			t.Errorf("regIncBeta returned NaN for a=%v b=%v x=%v", v.a, v.b, v.x)
		}
		if got < 0 || got > 1 {
			t.Errorf("regIncBeta out of bounds [0,1]: %v (a=%v b=%v x=%v)", got, v.a, v.b, v.x)
		}
	}
}

func TestClampTiny(t *testing.T) {
	// value near zero
	if got := clampTiny(1e-40); got != 1e-30 {
		t.Errorf("clampTiny did not clamp near‑zero value, got %v", got)
	}
	// normal value unchanged
	v := 0.12345
	if got := clampTiny(v); got != v {
		t.Errorf("clampTiny altered non‑tiny value, got %v want %v", got, v)
	}
}

func TestLgammaBeta(t *testing.T) {
	cases := []struct{ a, b float64 }{{2, 3}, {0.5, 0.5}, {5, 2}}
	for _, c := range cases {
		want := func() float64 {
			la, _ := math.Lgamma(c.a)
			lb, _ := math.Lgamma(c.b)
			lab, _ := math.Lgamma(c.a + c.b)
			return la + lb - lab
		}()
		got := lgammaBeta(c.a, c.b)
		if !ttestApproxEqual(got, want) {
			t.Errorf("lgammaBeta(%v,%v) = %v, want %v", c.a, c.b, got, want)
		}
	}
}

func TestTSf(t *testing.T) {
	cases := []struct{ t, df float64 }{{1.2, 10}, {0.0, 5}, {2.5, 20}}
	for _, c := range cases {
		x := c.df / (c.df + c.t*c.t)
		want := 0.5 * regIncBeta(c.df/2.0, 0.5, x)
		got := tSf(c.t, c.df)
		if !ttestApproxEqual(got, want) {
			t.Errorf("tSf(%v,%v) = %v, want %v", c.t, c.df, got, want)
		}
	}
}

func TestTTest_OneSample_Uncovered(t *testing.T) {
	data := Float64Data{2, 4, 6, 8}
	popMean := 0.0
	gotT, gotP, err := TTest(data, nil, popMean)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Expected values computed using the same formulas as TTest.
	mean := 5.0
	var sumSq float64
	for _, v := range data {
		diff := v - mean
		sumSq += diff * diff
	}
	var1 := sumSq / float64(len(data)-1)
	sd := math.Sqrt(var1)
	se := sd / math.Sqrt(float64(len(data)))
	expectedT := (mean - popMean) / se
	df := float64(len(data) - 1)
	expectedP := 2 * tSf(math.Abs(expectedT), df)

	const eps = 1e-9
	if math.Abs(gotT-expectedT) > eps {
		t.Errorf("t mismatch: got %v want %v", gotT, expectedT)
	}
	if math.Abs(gotP-expectedP) > eps {
		t.Errorf("pvalue mismatch: got %v want %v", gotP, expectedP)
	}
}
