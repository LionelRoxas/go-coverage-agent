package stats

import (
	"errors"
	"math"
	"testing"
)

func TestDiff(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{"empty", Float64Data{}, nil, ErrEmptyInput},
		{"normal", Float64Data{1, 3, 2, 5}, []float64{2, -1, 3}, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Diff(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr != nil {
				if got != nil {
					t.Fatalf("expected nil slice on error, got %v", got)
				}
				return
			}
			if len(got) != len(tc.want) {
				t.Fatalf("length mismatch: got %d, want %d", len(got), len(tc.want))
			}
			for i := range got {
				if math.Abs(got[i]-tc.want[i]) > 1e-12 {
					t.Fatalf("at index %d: got %v, want %v", i, got[i], tc.want[i])
				}
			}
		})
	}
}

func TestPercentChange(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
		check   func([]float64) bool // optional extra checks
	}{
		{"empty", Float64Data{}, nil, ErrEmptyInput, nil},
		{"normal", Float64Data{1, 3, 2, 5}, []float64{2, -1.0 / 3.0, 1.5}, nil, nil},
		{
			"zeroDenom",
			Float64Data{0, 0, 2},
			[]float64{math.NaN(), math.Inf(1)},
			nil,
			func(res []float64) bool {
				if len(res) != 2 {
					return false
				}
				if !math.IsNaN(res[0]) {
					return false
				}
				if !math.IsInf(res[1], 1) {
					return false
				}
				return true
			},
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PercentChange(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr != nil {
				if got != nil {
					t.Fatalf("expected nil slice on error, got %v", got)
				}
				return
			}
			if tc.check != nil {
				if !tc.check(got) {
					t.Fatalf("custom check failed for result %v", got)
				}
				return
			}
			if len(got) != len(tc.want) {
				t.Fatalf("length mismatch: got %d, want %d", len(got), len(tc.want))
			}
			for i := range got {
				if math.IsNaN(tc.want[i]) {
					if !math.IsNaN(got[i]) {
						t.Fatalf("at index %d: expected NaN, got %v", i, got[i])
					}
					continue
				}
				if math.IsInf(tc.want[i], 0) {
					sign := 1
					if tc.want[i] < 0 {
						sign = -1
					}
					if !math.IsInf(got[i], sign) {
						t.Fatalf("at index %d: expected Inf(%d), got %v", i, sign, got[i])
					}
					continue
				}
				if math.Abs(got[i]-tc.want[i]) > 1e-12 {
					t.Fatalf("at index %d: got %v, want %v", i, got[i], tc.want[i])
				}
			}
		})
	}
}

func TestFloat64Data_Diff(t *testing.T) {
	input := Float64Data{10, 7, 9}
	want := []float64{-3, 2}
	got, err := input.Diff()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != len(want) {
		t.Fatalf("length mismatch: got %d, want %d", len(got), len(want))
	}
	for i := range got {
		if math.Abs(got[i]-want[i]) > 1e-12 {
			t.Fatalf("at index %d: got %v, want %v", i, got[i], want[i])
		}
	}
}

func TestFloat64Data_PercentChange(t *testing.T) {
	input := Float64Data{2, 4, 1}
	// (4-2)/2 = 1, (1-4)/4 = -0.75
	want := []float64{1, -0.75}
	got, err := input.PercentChange()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != len(want) {
		t.Fatalf("length mismatch: got %d, want %d", len(got), len(want))
	}
	for i := range got {
		if math.Abs(got[i]-want[i]) > 1e-12 {
			t.Fatalf("at index %d: got %v, want %v", i, got[i], want[i])
		}
	}
}
