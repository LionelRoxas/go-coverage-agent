package stats

import (
	"errors"
	"math"
	"testing"
)

func kendallApproxEqual(got, want float64) bool {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= eps
}

func TestKendallTau(t *testing.T) {
	cases := []struct {
		name    string
		data1   []float64
		data2   []float64
		want    float64
		wantErr error
	}{
		{"empty input", []float64{}, []float64{}, math.NaN(), ErrEmptyInput},
		{"size mismatch", []float64{1, 2}, []float64{1}, math.NaN(), ErrSize},
		{"all tied", []float64{5, 5, 5}, []float64{5, 5, 5}, 0, nil},
		{"perfect concordance", []float64{1, 2, 3}, []float64{1, 2, 3}, 1, nil},
		{"mixed with ties", []float64{1, 2, 2}, []float64{1, 2, 3}, 2 / math.Sqrt(6), nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := KendallTau(tc.data1, tc.data2)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if !kendallApproxEqual(got, tc.want) {
					t.Fatalf("expected %v, got %v", tc.want, got)
				}
			} else {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
			}
		})
	}
}

func TestFloat64Data_KendallTau(t *testing.T) {
	d1 := Float64Data{1, 2, 3}
	d2 := Float64Data{1, 2, 3}
	got, err := d1.KendallTau(d2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !kendallApproxEqual(got, 1) {
		t.Fatalf("expected 1, got %v", got)
	}
}

func TestKendallTau_TiedYAndDiscordant(t *testing.T) {
	cases := []struct {
		name  string
		data1 Float64Data
		data2 Float64Data
		want  float64
	}{
		{
			name:  "tiedY and discordant",
			data1: Float64Data{1, 2, 3},
			data2: Float64Data{5, 5, 1},
			// Expected value computed as -(2) / sqrt(2*3) = -0.816496580927726
			want: -0.816496580927726,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := KendallTau(tc.data1, tc.data2)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("got %v want %v", got, tc.want)
			}
		})
	}
}

func TestKendallTau_AllTiedBothVariables(t *testing.T) {
	data1 := Float64Data{1, 1, 1}
	data2 := Float64Data{2, 2, 2}
	got, err := KendallTau(data1, data2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != 0 {
		t.Fatalf("expected 0, got %v", got)
	}
}
