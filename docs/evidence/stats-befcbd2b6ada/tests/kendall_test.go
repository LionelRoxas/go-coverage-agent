package stats

import (
	"errors"
	"math"
	"testing"
)

func kendallApproxEqual(t *testing.T, got, want float64) {
	if math.IsNaN(got) && math.IsNaN(want) {
		return
	}
	if math.Abs(got-want) > 1e-9 {
		t.Errorf("result mismatch: got %v want %v", got, want)
	}
}

func TestKendallTau_Errors(t *testing.T) {
	cases := []struct {
		name    string
		d1, d2  Float64Data
		wantErr error
		wantNaN bool
	}{
		{"EmptyFirst", Float64Data{}, Float64Data{1, 2}, ErrEmptyInput, true},
		{"EmptySecond", Float64Data{1, 2}, Float64Data{}, ErrEmptyInput, true},
		{"SizeMismatch", Float64Data{1, 2}, Float64Data{1, 2, 3}, ErrSize, true},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := KendallTau(tc.d1, tc.d2)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantNaN && !math.IsNaN(got) {
				t.Fatalf("expected NaN result, got %v", got)
			}
		})
	}
}

func TestKendallTau_Boundary(t *testing.T) {
	cases := []struct {
		name    string
		d1, d2  Float64Data
		want    float64
		wantErr error
	}{
		{"SingleElement", Float64Data{5}, Float64Data{10}, 0, nil},
		{"AllTied", Float64Data{1, 1, 1}, Float64Data{2, 2, 2}, 0, nil},
		{"PerfectAgreement", Float64Data{1, 2, 3}, Float64Data{1, 2, 3}, 1, nil},
		{"PerfectDisagreement", Float64Data{1, 2, 3}, Float64Data{3, 2, 1}, -1, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := KendallTau(tc.d1, tc.d2)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			kendallApproxEqual(t, got, tc.want)
		})
	}
}

func TestFloat64Data_KendallTau_Forward(t *testing.T) {
	d1 := Float64Data{1, 2, 3}
	d2 := Float64Data{3, 2, 1}
	got, err := d1.KendallTau(d2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	kendallApproxEqual(t, got, -1)
}

func TestKendallTau_TiedX(t *testing.T) {
	data1 := Float64Data{1, 1}
	data2 := Float64Data{2, 3}
	got, err := KendallTau(data1, data2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != 0 {
		t.Errorf("expected 0, got %v", got)
	}
}

func TestKendallTau_TiedY(t *testing.T) {
	data1 := Float64Data{2, 3}
	data2 := Float64Data{1, 1}
	got, err := KendallTau(data1, data2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != 0 {
		t.Errorf("expected 0, got %v", got)
	}
}

func TestKendallTau_MixedTies(t *testing.T) {
	cases := []struct {
		name string
		d1   Float64Data
		d2   Float64Data
		want float64
	}{
		{
			name: "mixed ties with concordant",
			d1:   Float64Data{1, 1, 2},
			d2:   Float64Data{1, 2, 2},
			want: 0.5,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := KendallTau(tc.d1, tc.d2)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			kendallApproxEqual(t, got, tc.want)
		})
	}
}
