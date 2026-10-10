package stats

import (
	"math"
	"testing"
)

func TestRegIncBeta_EdgeAndProperty(t *testing.T) {
	// Edge cases x=0 and x=1
	if got := regIncBeta(2.0, 3.0, 0.0); got != 0.0 {
		t.Fatalf("regIncBeta with x=0 returned %v, want 0", got)
	}
	if got := regIncBeta(2.0, 3.0, 1.0); got != 1.0 {
		t.Fatalf("regIncBeta with x=1 returned %v, want 1", got)
	}
	// Property I_x(a,b) + I_{1-x}(b,a) = 1
	a, b, x := 2.5, 1.5, 0.3
	i1 := regIncBeta(a, b, x)
	i2 := regIncBeta(b, a, 1.0-x)
	if math.Abs(i1+i2-1.0) > 1e-9 {
		t.Fatalf("regularized beta property failed: %v + %v != 1", i1, i2)
	}
}

func TestLgammaBeta(t *testing.T) {
	a, b := 2.3, 4.7
	got := lgammaBeta(a, b)
	la, _ := math.Lgamma(a)
	lb, _ := math.Lgamma(b)
	lab, _ := math.Lgamma(a + b)
	want := la + lb - lab
	if math.Abs(got-want) > 1e-12 {
		t.Fatalf("lgammaBeta = %v, want %v", got, want)
	}
}

func TestClampTiny(t *testing.T) {
	cases := []struct {
		v    float64
		want float64
	}{
		{0.0, 1e-30},
		{1e-31, 1e-30},
		{-1e-31, 1e-30},
		{0.5, 0.5},
	}
	for _, tc := range cases {
		got := clampTiny(tc.v)
		if math.Abs(got-tc.want) > 1e-12 {
			t.Fatalf("clampTiny(%v) = %v, want %v", tc.v, got, tc.want)
		}
	}
}

func TestTSf(t *testing.T) {
	df := 10.0
	// t = 0 should give survival = 0.5
	if got := tSf(0.0, df); math.Abs(got-0.5) > 1e-12 {
		t.Fatalf("tSf(0, %v) = %v, want 0.5", df, got)
	}
	// Survival should decrease as |t| increases
	high := tSf(5.0, df)
	if !(high < 0.5) {
		t.Fatalf("tSf(5, %v) = %v, expected < 0.5", df, high)
	}
}

func TestTTest(t *testing.T) {
	cases := []struct {
		name    string
		data1   Float64Data
		data2   Float64Data
		popMean float64
		wantErr error
		wantT   float64
		wantP   float64
		checkP  bool
	}{
		{
			name:    "Empty input returns ErrEmptyInput",
			data1:   Float64Data{},
			data2:   nil,
			popMean: 0,
			wantErr: ErrEmptyInput,
		},
		{
			name:    "One-sample with single element returns ErrBounds",
			data1:   Float64Data{5},
			data2:   nil,
			popMean: 0,
			wantErr: ErrBounds,
		},
		{
			name:    "One-sample zero variance matches population mean returns t=0 p=1",
			data1:   Float64Data{3, 3, 3},
			data2:   nil,
			popMean: 3,
			wantT:   0,
			wantP:   1.0,
		},
		{
			name:    "One-sample zero variance not matching population mean returns ErrBounds",
			data1:   Float64Data{3, 3, 3},
			data2:   nil,
			popMean: 4,
			wantErr: ErrBounds,
		},
		{
			name:    "Two-sample insufficient total size returns ErrBounds",
			data1:   Float64Data{1},
			data2:   Float64Data{2},
			popMean: 0,
			wantErr: ErrBounds,
		},
		{
			name:    "Two-sample normal case computes correct t and p in [0,1]",
			data1:   Float64Data{1, 2, 3},
			data2:   Float64Data{4, 5, 6},
			popMean: 0,
			wantT:   -3.674234614174767,
			checkP:  true,
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			gotT, gotP, err := TTest(tc.data1, tc.data2, tc.popMean)
			if tc.wantErr != nil {
				if err != tc.wantErr {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			// compare t statistic
			if math.IsNaN(tc.wantT) {
				if !math.IsNaN(gotT) {
					t.Fatalf("expected t NaN, got %v", gotT)
				}
			} else {
				if math.Abs(gotT-tc.wantT) > 1e-9 {
					t.Fatalf("t mismatch: want %v got %v", tc.wantT, gotT)
				}
			}
			// compare p-value
			if tc.checkP {
				if gotP < 0 || gotP > 1 {
					t.Fatalf("pvalue out of range [0,1]: %v", gotP)
				}
			} else {
				if math.Abs(gotP-tc.wantP) > 1e-9 {
					t.Fatalf("pvalue mismatch: want %v got %v", tc.wantP, gotP)
				}
			}
		})
	}
}
