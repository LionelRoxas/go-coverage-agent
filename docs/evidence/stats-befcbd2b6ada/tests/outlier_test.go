package stats

import (
	"errors"
	"math"
	"reflect"
	"testing"
)

func TestQuartileOutliers_EmptyInput(t *testing.T) {
	var input Float64Data
	_, err := QuartileOutliers(input)
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr, got %v", err)
	}
}

func TestQuartileOutliers_OutlierClassification(t *testing.T) {
	input := Float64Data{9, 1, 5, 2, 8, 3, 7, 4, 6, 20, 30}
	out, err := QuartileOutliers(input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	wantMild := Float64Data{20}
	wantExtreme := Float64Data{30}
	if !reflect.DeepEqual(out.Mild, wantMild) {
		t.Errorf("mild outliers = %v, want %v", out.Mild, wantMild)
	}
	if !reflect.DeepEqual(out.Extreme, wantExtreme) {
		t.Errorf("extreme outliers = %v, want %v", out.Extreme, wantExtreme)
	}
}

func TestQuartileOutliers_QuartileBehavior(t *testing.T) {
	cases := []struct {
		name      string
		input     Float64Data
		expectErr bool
	}{
		{"NaNInput", Float64Data{math.NaN(), 1, 2}, false},
		{"SingleElement", Float64Data{5}, true},
	}
	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			got, err := QuartileOutliers(tc.input)
			if tc.expectErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got.Mild) != 0 || len(got.Extreme) != 0 {
				t.Errorf("expected empty outliers, got mild=%v extreme=%v", got.Mild, got.Extreme)
			}
		})
	}
}
